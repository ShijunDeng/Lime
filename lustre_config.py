# Copyright (c) 2017 DataDirect Networks, Inc.
# All Rights Reserved.
# Author: lixi@ddn.com
"""
Config Lustre using SSH connection
"""

import re
import logging

# local libs
import ssh_host


class LustreDevice(object):
    def __init__(self, cluster, type, index, host):
        self.ld_cluster = cluster
        self.ld_type = type
        self.ld_index = index
        self.ld_host = host


def find_device_in_list(devices, type, index):
    for device in devices:
        if device.ld_type == type and device.ld_index == index:
            return device
    return None


def version_value(major, minor, patch):
    value = (major << 16) | (minor << 8) | patch
    return value


def tbf_escape_name(name):
    good_name = ""
    for char in name:
        if char.isalnum() or char == "_":
            good_name += char
        else:
            good_name += "_"
    return good_name


class LustreHost(ssh_host.SSHHost):
    """
    Eacho host in a Lustre clustre has an object of LustreHost
    """
    def __init__(self, cluster, hostname, identity_file=None):
        super(LustreHost, self).__init__(hostname, identity_file=identity_file)
        self.lh_devices = []
        self.lh_cluster = cluster
        self.lh_detect_version()

    def lh_detect_devices(self, cluster_devices):
        logging.debug("detecting devices on host [%s]", self.sh_hostname)
        devices = []

        command = ("lctl dl")
        retval = self.sh_run(command)
        if retval.cr_exit_status != 0:
            logging.error("failed to run command [%s] on host [%s], "
                          "ret = [%d], stdout = [%s], stderr = [%s]",
                          command, self.sh_hostname,
                          retval.cr_exit_status,
                          retval.cr_stdout,
                          retval.cr_stderr)
            return -1

        logging.debug("command [%s] output on host [%s]: [%s]",
                      command, self.sh_hostname, retval.cr_stdout)
        for line in retval.cr_stdout.splitlines():
            logging.debug("checking line [%s]", line)
            match = self.lh_cluster.lc_mdt_regular.match(line)
            if match:
                mdt_index = match.group("mdt_index")
                device_name = ("%s-MDT%s" % (self.lh_cluster.lc_fsname, mdt_index))
                logging.debug("device [%s] running on host [%s]",
                              device_name, self.sh_hostname)
                device = find_device_in_list(cluster_devices, "MDT", mdt_index)
                if device is not None:
                    logging.error("two hosts [%s] and [%s] for device [%s]",
                                  device.ld_host.sh_hostname,
                                  self.sh_hostname, device_name)
                    return -1
                device = LustreDevice(self.lh_cluster, "MDT", mdt_index, self)
                cluster_devices.append(device)
                devices.append(device)

            match = self.lh_cluster.lc_ost_regular.match(line)
            if match:
                ost_index = match.group("ost_index")
                device_name = ("%s-OST%s" % (self.lh_cluster.lc_fsname, ost_index))
                logging.debug("device [%s] running on host [%s]",
                              device_name, self.sh_hostname)
                device = find_device_in_list(cluster_devices, "OST", ost_index)
                if device is not None:
                    logging.error("two hosts [%s] and [%s] for device [%s]",
                                  device.ld_host.sh_hostname,
                                  self.sh_hostname, device_name)
                    return -1
                device = LustreDevice(self.lh_cluster, "OST", ost_index, self)
                cluster_devices.append(device)
                devices.append(device)

            match = self.lh_cluster.lc_mgs_pattern.match(line)
            if match:
                device_name = "MGS"
                logging.debug("device [%s] running on host [%s]",
                              device_name, self.sh_hostname)
                device = find_device_in_list(cluster_devices, "MGS", 0)
                if device is not None:
                    logging.error("two hosts [%s] and [%s] for device [%s]",
                                  device.ld_host.sh_hostname,
                                  self.sh_hostname, device_name)
                device = LustreDevice(self.lh_cluster, "MGS", 0, self)
                cluster_devices.append(device)
                devices.append(device)
        self.lh_devices = devices
        return 0

    def lh_enable_tbf_for_ost_io(self, tbf_type):
        command = ("echo -n tbf %s > /proc/fs/lustre/ost/OSS/ost_io/nrs_policies" % tbf_type)
        retval = self.sh_run(command)
        if retval.cr_exit_status != 0:
            logging.error("failed to run command [%s] on host [%s], "
                          "ret = [%d], stdout = [%s], stderr = [%s]",
                          command, self.sh_hostname,
                          retval.cr_exit_status,
                          retval.cr_stdout,
                          retval.cr_stderr)
            return -1
        return 0

    def lh_enable_fifo_for_ost_io(self):
        command = ("echo -n fifo > /proc/fs/lustre/ost/OSS/ost_io/nrs_policies")
        retval = self.sh_run(command)
        if retval.cr_exit_status != 0:
            logging.error("failed to run command [%s] on host [%s], "
                          "ret = [%d], stdout = [%s], stderr = [%s]",
                          command, self.sh_hostname,
                          retval.cr_exit_status,
                          retval.cr_stdout,
                          retval.cr_stderr)
            return -1
        return 0

    def lh_set_jobid_var(self, jobid_var):
        command = ("lctl conf_param %s.sys.jobid_var=%s" %
                   (self.lh_cluster.lc_fsname, jobid_var))
        retval = self.sh_run(command)
        if retval.cr_exit_status != 0:
            logging.error("failed to run command [%s] on host [%s], "
                          "ret = [%d], stdout = [%s], stderr = [%s]",
                          command, self.sh_hostname,
                          retval.cr_exit_status,
                          retval.cr_stdout,
                          retval.cr_stderr)
            return -1
        return 0

    def lh_start_tbf_rule(self, name, expression, rate):
        # For Lustre version ealier than 2.8.54, no "rate=" or "jobid=" is needed
        if self.lh_version_value >= version_value(2, 8, 54):
            command = ("echo -n start %s jobid={%s} rate=%d > /proc/fs/lustre/ost/OSS/ost_io/nrs_tbf_rule" %
                (name, expression, rate))
        else:
            command = ("echo -n start %s {%s} %d > /proc/fs/lustre/ost/OSS/ost_io/nrs_tbf_rule" %
                (name, expression, rate))
        retval = self.sh_run(command)
        if retval.cr_exit_status != 0:
            logging.error("failed to run command [%s] on host [%s], "
                          "ret = [%d], stdout = [%s], stderr = [%s]",
                          command, self.sh_hostname,
                          retval.cr_exit_status,
                          retval.cr_stdout,
                          retval.cr_stderr)
            return -1
        return 0

    def lh_change_tbf_rate(self, name, rate):
        if self.lh_version_value >= version_value(2, 8, 54):
            command = ("echo -n change %s rate=%d > /proc/fs/lustre/ost/OSS/ost_io/nrs_tbf_rule" %
                (name, rate))
        else:
            command = ("echo -n change %s %d > /proc/fs/lustre/ost/OSS/ost_io/nrs_tbf_rule" %
                (name, rate))
        retval = self.sh_run(command)
        if retval.cr_exit_status != 0:
            logging.error("failed to run command [%s] on host [%s], "
                          "ret = [%d], stdout = [%s], stderr = [%s]",
                          command, self.sh_hostname,
                          retval.cr_exit_status,
                          retval.cr_stdout,
                          retval.cr_stderr)
            return -1
        return 0

    def lh_detect_version(self):
        command = ("cat /proc/fs/lustre/version | grep lustre: | awk '{print $2}'")
        retval = self.sh_run(command)
        if retval.cr_exit_status != 0:
            logging.error("failed to run command [%s] on host [%s], "
                          "ret = [%d], stdout = [%s], stderr = [%s]",
                          command, self.sh_hostname,
                          retval.cr_exit_status,
                          retval.cr_stdout,
                          retval.cr_stderr)
            self.lh_lustre_version = None
            return -1
        self.lh_lustre_version_string = retval.cr_stdout.strip()
        version_pattern = r"^(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)\.(?P<fix>\d+)$"
        version_regular = re.compile(version_pattern)
        match = version_regular.match(self.lh_lustre_version_string)
        if match:
            self.lh_lustre_version_major = int(match.group("major"))
            self.lh_lustre_version_minor = int(match.group("minor"))
            self.lh_lustre_version_patch = int(match.group("patch"))
            self.lh_lustre_version_fix = int(match.group("fix"))
        else:
            logging.error("unexpected version string format: %s",
                          self.lh_lustre_version_string)
            return -1

        self.lh_version_value = version_value(self.lh_lustre_version_major,
            self.lh_lustre_version_minor, self.lh_lustre_version_patch)
        logging.debug("version_string: %s %d", self.lh_lustre_version_string,
            self.lh_version_value)
        return 0


class LustreCluster(object):
    """
    Each Lustre cluster has an object of LustreCluster
    """
    def __init__(self, fsname, server_hostnames, ssh_identity_file=None):
        self.lc_hosts = []
        self.lc_fsname = fsname
        mdt_pattern = (r"^.+ UP mdt %s-MDT(?P<mdt_index>\S+) .+$" %
                       self.lc_fsname)
        logging.debug("mdt_pattern: [%s]", mdt_pattern)
        self.lc_mdt_regular = re.compile(mdt_pattern)
        ost_pattern = (r"^.+ UP obdfilter %s-OST(?P<ost_index>\S+) .+$" %
                       self.lc_fsname)
        logging.debug("ost_pattern: [%s]", ost_pattern)
        self.lc_ost_regular = re.compile(ost_pattern)
        mgs_pattern = (r"^.+ UP mgs MGS MGS .+$")
        logging.debug("mgs_pattern: [%s]", mgs_pattern)
        self.lc_mgs_pattern = re.compile(mgs_pattern)
        for hostname in server_hostnames:
            host = LustreHost(self, hostname, identity_file=ssh_identity_file)
            self.lc_hosts.append(host)
        self.lc_devices = []

    def lc_detect_devices(self):
        devices = []
        for host in self.lc_hosts:
            ret = host.lh_detect_devices(devices)
            if ret:
                logging.error("failed to detect devices on host [%s]",
                              host.sh_hostname)
                return ret
        self.lc_devices = devices
        return 0

    def lc_enable_tbf_for_ost_io(self, tbf_type):
        hosts = []
        for device in self.lc_devices:
            if device.ld_type != "OST":
                continue
            if device.ld_host.sh_hostname in hosts:
                continue
            ret = device.ld_host.lh_enable_tbf_for_ost_io(tbf_type)
            if ret:
                logging.error("failed to enable TBF for ost_io on host [%s]",
                              device.ld_host.sh_hostname)
                return ret
            hosts.append(device.ld_host.sh_hostname)
        return 0

    def lc_set_jobid_var(self, jobid_var):
        done = False
        for device in self.lc_devices:
            if device.ld_type != "MGS":
                continue
            ret = device.ld_host.lh_set_jobid_var(jobid_var)
            if ret:
                logging.error("failed to set jobid_var on host [%s]",
                              device.ld_host.sh_hostname)
                return ret
            done = True
        if not done:
            logging.error("no MGS host found for cluster [%s]",
                          self.lc_fsname)
            return -1
        return 0

    def lc_enable_fifo_for_ost_io(self):
        hosts = []
        for device in self.lc_devices:
            if device.ld_type != "OST":
                continue
            if device.ld_host.sh_hostname in hosts:
                continue
            ret = device.ld_host.lh_enable_fifo_for_ost_io()
            if ret:
                logging.error("failed to disable TBF on host [%s]",
                              device.ld_host.sh_hostname)
                return ret
            hosts.append(device.ld_host.sh_hostname)
        return 0

    def lc_start_tbf_rule(self, name, expression, rate):
        hosts = []
        for device in self.lc_devices:
            if device.ld_type != "OST":
                continue
            if device.ld_host.sh_hostname in hosts:
                continue
            ret = device.ld_host.lh_start_tbf_rule(name, expression, rate)
            if ret:
                logging.error("failed to start TBF rule [%s] on host [%s]",
                              name, device.ld_host.sh_hostname)
                return ret
            hosts.append(device.ld_host.sh_hostname)
        return 0

    def lc_change_tbf_rate(self, name, rate):
        hosts = []
        for device in self.lc_devices:
            if device.ld_type != "OST":
                continue
            if device.ld_host.sh_hostname in hosts:
                continue
            ret = device.ld_host.lh_change_tbf_rate(name, rate)
            if ret:
                logging.error("failed to start TBF rule [%s] on host [%s]",
                              name, device.ld_host.sh_hostname)
                return ret
            hosts.append(device.ld_host.sh_hostname)
        return 0


if __name__ == "__main__":
    cluster = LustreCluster("lustre", ["10.0.0.24"])
    cluster.lc_detect_devices()
    cluster.lc_enable_tbf_for_ost_io("nid")
    cluster.lc_set_jobid_var("procname_uid")
