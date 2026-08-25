import QtQuick
import QtQuick.Window

// ============ 绝区零风格 Overlay HUD（样式写死，不读配置） ============
// 近黑底 #0d0d0d / 招牌黄 #ffd400 / 电光青 #00e5ff / 白字粗体
// 布局：log 左中 / state 右中 / decision 底部中 / performance 右上
// 左下角运行状态行贴边 margin=1

Window {
    id: root
    visible: false
    color: "transparent"
    flags: Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint

    // 面板可见性由 Python 侧注入（面板位置用 anchors 相对 HUD 窗口固定，不受分辨率影响）
    property bool logVisible: true
    property bool stateVisible: true
    property bool decisionVisible: true
    property bool perfVisible: true

    // 面板淡入淡出透明度（Python 侧驱动：信息 15 秒未更新则淡出，0 隐藏 1 全显）
    property real logFade: 0
    property real stateFade: 0
    property real decisionFade: 0

    // 左下角运行状态行（由 Python 注入）
    property string statusLine: ""

    // 当前节点轮次实时用时（由 Python 注入，格式如 "12.3ms"，空则不显示）
    property string operationDuration: ""

    // 自动战斗是否运行中（由 Python 注入，控制灵动岛流光动画）
    property bool isRunning: false

    // Fairy 徽章：三态（running/pause/stop，由 Python 注入）
    property string fairyState: "stop"

    // 决策面板标题栏文本（由 Python 注入，显示最新一条决策状态）
    property string decisionTitle: ""

    // 模式切换提示文本（由 Python 注入，如 "HUD 已关闭"，5 秒后自动消失）
    property string toastText: ""

    // 面板通用字体（写死）
    property string zhFont: "Microsoft YaHei"
    property string monoFont: "Consolas"

    // ============ 数据模型（Python 侧注入 OverlayListModel） ============
    // logModel / stateModel / decisionModel / perfModel
    // 由 OverlayHudWindow 通过 setContextProperty 注入，QML 不再自建 ListModel。

    // ============ 面板骨架（黑色底 + 黄标题条 + 青底条） ============
    // 每个面板：Rectangle 黑底细框，顶部黄条标题，底部青横线

    // ---------- 日志面板（左下角） ----------
    Item {
        id: logBox
        anchors.left: parent.left
        anchors.leftMargin: 4
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 4
        width: 460
        height: 300
        visible: root.logVisible
        opacity: root.logFade
        Behavior on opacity { NumberAnimation { duration: 400; easing.type: Easing.InOutQuad } }

        Rectangle {
            anchors.fill: parent
            color: "#0d0d0d"
            border.color: "#323232"
            border.width: 4
            radius: 8
            clip: true

            // 标题条：黄底黑字
            Rectangle {
                anchors.top: parent.top
                anchors.left: parent.left
                anchors.right: parent.right
                height: 34
                color: "#ffd400"
                topLeftRadius: 8
                topRightRadius: 8
                Text {
                    anchors.left: parent.left
                    anchors.leftMargin: 12
                    anchors.verticalCenter: parent.verticalCenter
                    text: "日志"
                    color: "#0d0d0d"
                    font.pixelSize: 17
                    font.bold: true
                    font.family: root.zhFont
                }
                Text {
                    anchors.right: parent.right
                    anchors.rightMargin: 12
                    anchors.verticalCenter: parent.verticalCenter
                    text: "LOG"
                    color: "#0d0d0d"
                    font.pixelSize: 12
                    font.bold: true
                    font.family: root.monoFont
                }
            }

            // 日志列表：级别色竖条 + 消息（等级只看竖条颜色，不显示时间/级别/模块）
            ListView {
                id: logList
                anchors.top: parent.top
                anchors.topMargin: 40
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                anchors.bottomMargin: 8
                clip: true
                model: logModel
                spacing: 3

                onCountChanged: positionViewAtEnd()

                delegate: Row {
                    width: logList.width
                    spacing: 6

                    Rectangle {
                        width: 4
                        height: 18
                        anchors.verticalCenter: parent.verticalCenter
                        color: model.levelColor
                    }

                    Text {
                        text: model.message
                        color: "#e8e8e8"
                        font.pixelSize: 14
                        font.bold: true
                        font.family: root.monoFont
                        width: logList.width - 14
                        elide: Text.ElideRight
                    }
                }
            }
        }
    }

    // ---------- 战斗状态面板（右下角，决策栏上方，窄高条） ----------
    Item {
        id: stateBox
        anchors.right: parent.right
        anchors.rightMargin: 4
        anchors.bottom: decisionBox.top
        anchors.bottomMargin: 8
        width: 200
        height: 600
        visible: root.stateVisible
        opacity: root.stateFade
        Behavior on opacity { NumberAnimation { duration: 400; easing.type: Easing.InOutQuad } }

        Rectangle {
            anchors.fill: parent
            color: "#0d0d0d"
            border.color: "#323232"
            border.width: 4
            radius: 8
            clip: true

            Rectangle {
                anchors.top: parent.top
                anchors.left: parent.left
                anchors.right: parent.right
                height: 34
                color: "#ffd400"
                topLeftRadius: 8
                topRightRadius: 8
                Text {
                    anchors.left: parent.left
                    anchors.leftMargin: 12
                    anchors.verticalCenter: parent.verticalCenter
                    text: "战斗状态"
                    color: "#0d0d0d"
                    font.pixelSize: 17
                    font.bold: true
                    font.family: root.zhFont
                }
                Text {
                    anchors.right: parent.right
                    anchors.rightMargin: 12
                    anchors.verticalCenter: parent.verticalCenter
                    text: "STATE"
                    color: "#0d0d0d"
                    font.pixelSize: 12
                    font.bold: true
                    font.family: root.monoFont
                }
            }

            GridView {
                id: stateGrid
                anchors.top: parent.top
                anchors.topMargin: 44
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                anchors.bottomMargin: 8
                clip: true
                model: stateModel
                // 单列固定行高，内容从顶部向下排，不均分
                cellWidth: width
                cellHeight: 22

                // 插入：从右侧抛物线滑入 + 淡入（无回弹）
                add: Transition {
                    NumberAnimation { property: "x"; from: stateGrid.width; to: 0; duration: 400; easing.type: Easing.OutCubic }
                    NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 300 }
                }
                // 移除：向右滑出 + 淡出
                remove: Transition {
                    NumberAnimation { property: "x"; to: stateGrid.width; duration: 250; easing.type: Easing.InCubic }
                    NumberAnimation { property: "opacity"; to: 0; duration: 200 }
                }

                delegate: Item {
                    width: stateGrid.cellWidth
                    height: stateGrid.cellHeight
                    clip: true

                    // 青色强调竖条（首行用黄色块徽标）
                    Rectangle {
                        width: 4
                        height: 14
                        anchors.left: parent.left
                        anchors.leftMargin: 6
                        anchors.verticalCenter: parent.verticalCenter
                        color: model.accent
                    }

                    Text {
                        id: stateKeyText
                        anchors.left: parent.left
                        anchors.leftMargin: 16
                        anchors.right: stateSecondsText.left
                        anchors.rightMargin: 4
                        anchors.verticalCenter: parent.verticalCenter
                        text: model.key
                        color: "#9a9a9a"
                        font.pixelSize: 12
                        font.bold: true
                        font.family: root.zhFont
                        elide: Text.ElideRight
                    }
                    Text {
                        id: stateSecondsText
                        anchors.right: stateValueText.left
                        anchors.rightMargin: 8
                        anchors.verticalCenter: parent.verticalCenter
                        text: model.value
                        color: "#00e5ff"
                        font.pixelSize: 12
                        font.bold: true
                        font.family: root.monoFont
                    }
                    Text {
                        id: stateValueText
                        anchors.right: parent.right
                        anchors.rightMargin: 8
                        anchors.verticalCenter: parent.verticalCenter
                        text: model.stateValue
                        color: model.valueColor
                        font.pixelSize: 14
                        font.bold: true
                        font.family: root.zhFont
                    }
                }
            }
        }
    }

    // ---------- 决策面板（右下角，固定 550x150） ----------
    Item {
        id: decisionBox
        anchors.right: parent.right
        anchors.rightMargin: 4
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 4
        width: 550
        height: 150
        visible: root.decisionVisible
        opacity: root.decisionFade
        Behavior on opacity { NumberAnimation { duration: 400; easing.type: Easing.InOutQuad } }

        Rectangle {
            anchors.fill: parent
            color: "#0d0d0d"
            border.color: "#323232"
            border.width: 4
            radius: 8
            clip: true

            Rectangle {
                anchors.top: parent.top
                anchors.left: parent.left
                anchors.right: parent.right
                height: 30
                color: "#ffd400"
                topLeftRadius: 8
                topRightRadius: 8
                Text {
                    id: decisionTitleText
                    anchors.left: parent.left
                    anchors.leftMargin: 12
                    anchors.right: parent.right
                    anchors.rightMargin: 70
                    anchors.verticalCenter: parent.verticalCenter
                    text: root.decisionTitle.length > 0 ? root.decisionTitle : "决策"
                    color: "#0d0d0d"
                    font.pixelSize: 16
                    font.bold: true
                    font.family: root.zhFont
                    elide: Text.ElideRight

                    // 标题内容更新时从右侧抛物线滑入（无回弹）
                    transform: Translate { id: titleTranslate; x: 0 }
                    onTextChanged: {
                        titleTranslate.x = 40
                        titleAnim.start()
                    }
                    NumberAnimation {
                        id: titleAnim
                        target: titleTranslate
                        property: "x"
                        to: 0
                        duration: 400
                        easing.type: Easing.OutCubic
                    }
                }
                Text {
                    anchors.right: parent.right
                    anchors.rightMargin: 12
                    anchors.verticalCenter: parent.verticalCenter
                    text: "DECISION"
                    color: "#0d0d0d"
                    font.pixelSize: 11
                    font.bold: true
                    font.family: root.monoFont
                }
            }

            ListView {
                id: decisionList
                anchors.top: parent.top
                anchors.topMargin: 36
                anchors.left: parent.left
                anchors.leftMargin: 12
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                anchors.bottomMargin: 6
                clip: true
                model: decisionModel
                spacing: 2

                delegate: Row {
                    width: decisionList.width - 24
                    spacing: 6

                    Text {
                        text: model.expr
                        color: "#d8e27f"
                        font.pixelSize: 13
                        font.bold: true
                        font.family: root.monoFont
                        width: decisionList.width - 30
                        elide: Text.ElideRight
                    }
                }
            }
        }
    }

    // ---------- 性能面板（右上，半透明黑底，紧凑三行） ----------
    Item {
        id: perfBox
        anchors.right: parent.right
        anchors.rightMargin: 4
        anchors.top: parent.top
        anchors.topMargin: 4
        width: 150
        height: 70
        visible: root.perfVisible

        Rectangle {
            anchors.fill: parent
            color: "#CC000000"
            radius: 6

            Column {
                anchors.fill: parent
                anchors.margins: 6
                spacing: 4

                Repeater {
                    model: perfModel
                    delegate: Row {
                        spacing: 6
                        Text {
                            text: model.name
                            color: "#ffffff"
                            font.pixelSize: 14
                            font.bold: true
                            font.family: root.monoFont
                        }
                        Text {
                            text: model.avgText + "(" + model.peakText + ")ms"
                            color: "#00e5ff"
                            font.pixelSize: 14
                            font.bold: true
                            font.family: root.monoFont
                        }
                    }
                }
            }
        }
    }

    // ---------- 顶部运行状态行（灵动岛样式：顶部居中黑胶囊，运行中流光旋转） ----------
    Row {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        anchors.topMargin: 4
        spacing: 8

        // fairy 徽章（位于胶囊左侧，36px 与胶囊同高）：
        // SVG 已裁剪掉透明留白（266x266 画布，圆心居中）
        // running=三角旋转 / pause=停转 / stop=半透明保留（防跳动）
        Item {
            id: fairyBadge
            width: 36
            height: 36
            visible: true
            anchors.verticalCenter: parent.verticalCenter

            Connections {
                target: root
                function onFairyStateChanged() {
                    if (root.fairyState === "stop") {
                        // 停止：缩小并半透明停留（保留占位，避免胶囊跳动）
                        fairyBadge.opacity = 0.35
                        fairyBadge.scale = 0.85
                        fairyBadge.rotation = 0
                    } else {
                        // 运行/暂停：钻出放大旋正
                        fairyBadge.opacity = 1
                        fairyBadge.scale = 1
                        fairyBadge.rotation = 0
                    }
                }
            }
            Component.onCompleted: {
                if (root.fairyState === "stop") {
                    fairyBadge.opacity = 0.35
                    fairyBadge.scale = 0.85
                } else {
                    fairyBadge.opacity = 1
                    fairyBadge.scale = 1
                }
            }

            Behavior on opacity { NumberAnimation { duration: 380; easing.type: Easing.OutCubic } }
            Behavior on scale { NumberAnimation { duration: 380; easing.type: Easing.OutCubic } }
            Behavior on rotation { NumberAnimation { duration: 380; easing.type: Easing.OutCubic } }

            // 外发光：青色椭圆光晕（Canvas 绘制，自身缓慢旋转模拟能量旋转）
            // running 时旋转，pause 停转，stop 熄灭（徽章本体仍半透明保留）
            Canvas {
                id: fairyGlow
                anchors.fill: parent
                anchors.margins: -14
                opacity: root.fairyState === "stop" ? 0 : 1
                Behavior on opacity { NumberAnimation { duration: 380; easing.type: Easing.OutCubic } }

                // 椭圆光晕逆时针旋转（8s 一圈，与三角顺时针反向，更有动感）
                NumberAnimation on rotation {
                    from: 360
                    to: 0
                    duration: 8000
                    loops: Animation.Infinite
                    running: root.fairyState === "running"
                }

                onPaint: {
                    var ctx = getContext("2d")
                    var w = width
                    var h = height
                    ctx.clearRect(0, 0, w, h)
                    ctx.save()
                    ctx.translate(w / 2, h / 2)
                    // 压扁成椭圆（高为宽的 72%），产生旋转感
                    ctx.scale(1, 0.72)
                    var r = w / 2
                    var grad = ctx.createRadialGradient(0, 0, r * 0.15, 0, 0, r)
                    grad.addColorStop(0, "rgba(0,229,255,0.9)")
                    grad.addColorStop(0.5, "rgba(0,229,255,0.45)")
                    grad.addColorStop(1, "rgba(0,229,255,0)")
                    ctx.fillStyle = grad
                    ctx.beginPath()
                    ctx.arc(0, 0, r, 0, Math.PI * 2)
                    ctx.fill()
                    ctx.restore()
                }
                onWidthChanged: requestPaint()
                onHeightChanged: requestPaint()
            }

            // 圆主体（底座）
            Image {
                id: fairyBadgeBase
                anchors.fill: parent
                source: fairyBadgeUrl
                sourceSize: Qt.size(parent.width, parent.height)
            }
            // 三角层（绕 SVG 圆心 193,203 旋转）
            Image {
                id: fairyTriImg
                anchors.fill: parent
                source: fairyTriUrl
                sourceSize: Qt.size(parent.width, parent.height)
                transform: Rotation {
                    id: fairyTriRot
                    origin.x: fairyTriImg.width / 2
                    origin.y: fairyTriImg.height / 2
                    angle: 0
                }
            }

            // 三角持续旋转：running 时转，pause/stop 停转
            NumberAnimation {
                id: fairySpin
                target: fairyTriRot
                property: "angle"
                from: 0
                to: 360
                duration: 6000
                loops: Animation.Infinite
                running: root.fairyState === "running"
            }
        }

        Rectangle {
            width: statusRow.implicitWidth + 32
            height: 36
            color: "#0d0d0d"
            radius: height / 2
            clip: true
            visible: statusLineText.text.length > 0

            // 边缘流光：黄/青两道光段沿胶囊圆角边框环绕流动（Fairy 运行中效果）
            Canvas {
                id: flowCanvas
                anchors.fill: parent
                visible: root.isRunning
                property real flowPos: 0

                NumberAnimation on flowPos {
                    from: 0
                    to: 1
                    duration: 2500
                    loops: Animation.Infinite
                    running: flowCanvas.visible
                }
                onFlowPosChanged: requestPaint()
                onWidthChanged: requestPaint()
                onHeightChanged: requestPaint()

                function pointAt(t) {
                    var w = width
                    var h = height
                    var r = h / 2
                    var lineLen = w - h
                    var arcLen = Math.PI * r
                    var P = 2 * lineLen + 2 * arcLen
                    var d = ((t % 1) + 1) % 1 * P
                    if (d < lineLen) return {x: r + d, y: 0}
                    d -= lineLen
                    if (d < arcLen) {
                        var a = d / r
                        return {x: w - r + r * Math.sin(a), y: r - r * Math.cos(a)}
                    }
                    d -= arcLen
                    if (d < lineLen) return {x: w - r - d, y: h}
                    d -= lineLen
                    var a2 = d / r
                    return {x: r - r * Math.sin(a2), y: h - r + r * Math.cos(a2)}
                }

                function traceArc(t0, t1) {
                    var ctx = getContext("2d")
                    if (!ctx) return
                    var P = 2 * (width - height) + 2 * Math.PI * height / 2
                    var seg = 32
                    ctx.beginPath()
                    for (var i = 0; i <= seg; i++) {
                        var p = pointAt(t0 + (t1 - t0) * i / seg)
                        if (i === 0) ctx.moveTo(p.x, p.y)
                        else ctx.lineTo(p.x, p.y)
                    }
                    ctx.stroke()
                }

                onPaint: {
                    var ctx = getContext("2d")
                    if (!ctx) return
                    ctx.clearRect(0, 0, width, height)
                    var P = 2 * (width - height) + 2 * Math.PI * height / 2
                    var flowLen = 64 / P
                    ctx.lineWidth = 3
                    ctx.lineCap = "round"
                    ctx.strokeStyle = "#ffd400"
                    traceArc(flowPos, flowPos + flowLen)
                    ctx.strokeStyle = "#00e5ff"
                    traceArc(flowPos + 0.5, flowPos + 0.5 + flowLen)
                }
            }

            Row {
                id: statusRow
                anchors.centerIn: parent
                spacing: 6

                Text {
                    id: statusLineText
                    text: root.statusLine
                    color: "#ffffff"
                    font.pixelSize: 17
                    font.bold: true
                    font.family: root.zhFont
                }
            }
        }

        Text {
            anchors.verticalCenter: parent.verticalCenter
            text: root.operationDuration
            color: "#00e5ff"
            font.pixelSize: 15
            font.bold: true
            font.family: root.monoFont
            visible: text.length > 0
        }
    }

    // ============ 模式切换 Toast（中间底部，iOS 风格淡入淡出，5 秒后消失） ============
    Item {
        id: modeToast
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 160
        width: toastLabel.width + 56
        height: 44
        visible: root.toastText.length > 0
        opacity: 0

        Rectangle {
            anchors.fill: parent
            color: "#cc0d0d0d"
            radius: 22
            border.color: "#323232"
            border.width: 1
        }

        Text {
            id: toastLabel
            anchors.centerIn: parent
            text: root.toastText
            color: "#ffffff"
            font.pixelSize: 15
            font.bold: true
            font.family: root.zhFont
        }

        // 淡入：toastText 设置后 200ms 从透明到不透明
        NumberAnimation on opacity {
            id: toastFadeIn
            from: 0
            to: 1
            duration: 200
            easing.type: Easing.OutCubic
        }

        // 淡出：5 秒后触发，结束后清空文本（visible 随之隐藏）
        NumberAnimation on opacity {
            id: toastFadeOut
            from: 1
            to: 0
            duration: 300
            easing.type: Easing.InCubic
            onFinished: root.toastText = ""
        }

        Timer {
            id: toastHideTimer
            interval: 5000
            onTriggered: toastFadeOut.start()
        }

        function show() {
            toastFadeOut.stop()
            toastFadeIn.start()
            toastHideTimer.restart()
        }
    }

    // 模式切换提示触发：toastText 变化时淡入并重启 5 秒计时
    onToastTextChanged: {
        if (root.toastText.length > 0) {
            modeToast.show()
        }
    }

    // ============ Python 调用入口 ============
    // 由 OverlayHudBridge 以 setContextProperty("hud", bridge) 注入后调用
}

