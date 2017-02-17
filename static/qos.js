/*
 * Copyright (c) 2016, DDN Storage Corporation.
 */
/*
 *
 * JavaScript library to show the html
 *
 * Author: Li Xi <lixi@ddn.com>
 */

var QOS = {
    NAME_PANEL: "panel",
    ID_PANEL: "panel",
    NAME_CONSOLE_CONTAINER: "console_container",
    ID_CONSOLE_CONTAINER: "#console_container",
    NAME_CONSOLE: "console",
    ID_CONSOLE: "#console",
};

function QoS(lime)
{
    this.qos_lime = lime;
}

QoS.prototype.qos_page_init = function()
{
    this.qos_console_init();
    this.qos_lime.l_fini_func = this.qos_page_fini;
    this.qos_lime.l_navigation.na_activate_key(NAVIGATION.KEY_QOS);
}


QoS.prototype.qos_console_init = function()
{
    if (window.WebSocket == undefined) {
        console.error("WebSocket is not supported, no console");
        return
    }

    var string = '<div id="' + QOS.NAME_PANEL + '" class="panel"></div>';
    $(string).appendTo("#content");
    var mychart = echarts.init(document.getElementById(QOS.NAME_PANEL));
    var option = {
        series: [
            {
                name: 'Write Performance',
                min: 0,
                max: 1000,
                splitNumber:10,
                type: 'gauge',
                detail: {formatter:'{value}'},
                data: [{value: 0, name: 'MB/s'}],

                axisLine: {
                    lineStyle: {
                        color: [[0.09, 'lime'],[0.82, '#1e90ff'],[1, '#ff4500']],
                        width: 3,
                        shadowBlur: 10
                    }
                },

                axisLabel: {
                    textStyle: {
                        fontSize: 8,
                    }
                },

                axisTick: {
                    length :10,
                    lineStyle: {
                        color: 'auto',
                    }
                },
                splitLine: {
                    length :20,
                    lineStyle: {
                        color: 'auto',
                    }
                },
                title : {
                    textStyle: {
                        fontSize: 10,
                    }
                },
                detail : {
                    textStyle: {
                        fontWeight: 'bolder',
                        fontSize: 10,
                    }
                },
            }
        ]
    };

    string = '<div id="' + QOS.NAME_CONSOLE_CONTAINER +
        '" class="console_container"></div>';
    $(string).appendTo("#content");

    string = '<pre id="' + QOS.NAME_CONSOLE +
        '" class="console"></pre>';
    $(string).appendTo(QOS.ID_CONSOLE_CONTAINER);
    var data_string = JSON.stringify(
        this.qos_lime.l_control_table.ct_config,
        null, 4);

    var ws_url = 'ws://'+ window.location.hostname +
        (window.location.port ? ':' + window.location.port : '') +
        '/console_websocket';

    var websocket = new WebSocket(ws_url);
    var workspace = this.rc_result_title;
    websocket.onopen = function(evt) {
        websocket.send(data_string);
    };
    websocket.onclose = function(evt) {
    };
    websocket.onmessage = function(evt) {
        var message = JSON.parse(evt.data);
        var console_message = message.console
        var string = $(QOS.ID_CONSOLE).text() + console_message;
        var rate = message.rate
        $(QOS.ID_CONSOLE).text(string);
        $(QOS.ID_CONSOLE_CONTAINER).scrollTop($(QOS.ID_CONSOLE_CONTAINER)[0].scrollHeight);
        option.series[0].data[0].value = rate;
        mychart.setOption(option, true);
    };
    websocket.onerror = function(evt) {
        console.log("onerror");
    };
    /*
    setInterval(function () {
        option.series[0].data[0].value = (Math.random() * 1000).toFixed(2) - 0;
        mychart.setOption(option, true);
    },2000);
    */
}

QoS.prototype.qos_page_fini = function()
{
    $(QOS.ID_CONSOLE_CONTAINER).remove();
}
