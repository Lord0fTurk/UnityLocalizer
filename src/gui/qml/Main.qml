import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import QtQuick.Layouts
import QtQuick.Window
import "views"
import "components"

ApplicationWindow {
    id: window
    // Restore the previous session's size (clamped to this screen) and maximized state.
    readonly property var savedGeometry: appBackend ? appBackend.windowGeometry : ({})
    property int normalWidth: width
    property int normalHeight: height
    width: Math.min(savedGeometry.width > 0 ? savedGeometry.width : 1280, Screen.desktopAvailableWidth * 0.95)
    height: Math.min(savedGeometry.height > 0 ? savedGeometry.height : 800, Screen.desktopAvailableHeight * 0.95)
    minimumWidth: 980
    minimumHeight: 640
    visible: true
    Component.onCompleted: {
        if (savedGeometry.maximized) window.showMaximized();
    }
    onWidthChanged: { if (visibility === Window.Windowed) normalWidth = width; }
    onHeightChanged: { if (visibility === Window.Windowed) normalHeight = height; }
    onClosing: {
        if (appBackend) appBackend.saveWindowState(normalWidth, normalHeight, visibility === Window.Maximized);
    }

    function t(key) {
        return (localeManager && localeManager.currentLanguage, localeManager ? localeManager.t(key) : "");
    }

    title: "UnityLocalizer — " + window.t("dashboard.title") + " (v" + (appBackend ? appBackend.version : "0.1.0") + ")"
    color: Theme.canvas

    Material.theme: Theme.isDark ? Material.Dark : Material.Light
    Material.accent: Theme.accentSolid

    // ── Universal Multi-Theme Desktop UI System (DESIGN.md v2.1) ──
    readonly property color clrBg:         Theme.canvas
    readonly property color clrSidebar:    Theme.surfaceSidebar
    readonly property color clrSidebarTop: Theme.surfaceSidebar
    readonly property color clrCard:       Theme.surfaceCard
    readonly property color clrCardHover:  Theme.surfaceHover
    readonly property color clrCardBorder: Theme.borderCard
    readonly property color clrBorderGlow: Theme.accentHover
    readonly property color clrInput:      Theme.surfaceControl
    readonly property color clrAccent:     Theme.accentSolid
    readonly property color clrAccent2:    Theme.accentHover
    readonly property color clrPurple:     Theme.preset === "indigo" ? Theme.accentSolid : "#A855F7"
    readonly property color clrSuccess:    Theme.statusSuccess
    readonly property color clrWarn:       Theme.statusWarning
    readonly property color clrError:      Theme.statusDanger
    readonly property color clrTxt:        Theme.textPrimary
    readonly property color clrTxt2:       Theme.textSecondary
    readonly property color clrTxtDim:     Theme.textMuted

    property int navIndex: 0

    RowLayout {
        anchors.fill: parent
        spacing: 0

        // ════════════════════════════════════════════════════════════════════
        // 1. SOL KENAR ÇUBUĞU (SIDEBAR NAVIGATION - 240px)
        // ════════════════════════════════════════════════════════════════════
        Rectangle {
            Layout.preferredWidth: 240
            Layout.fillHeight: true
            color: clrSidebar

            Rectangle {
                anchors.right: parent.right
                width: 1
                height: parent.height
                color: clrCardBorder
            }

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 18
                spacing: 12

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 12

                    Rectangle {
                        Layout.preferredWidth: 44
                        Layout.preferredHeight: 44
                        radius: 12
                        color: Theme.accentAlpha(0.12)
                        border.color: Theme.accentAlpha(0.3)
                        border.width: 1

                        Image {
                            anchors.fill: parent
                            anchors.margins: 4
                            source: appBackend ? appBackend.get_asset_url("icon.png") : ""
                            sourceSize: Qt.size(128, 128)
                            fillMode: Image.PreserveAspectFit
                            smooth: true
                            mipmap: true
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 3

                        Label {
                            text: "UnityLocalizer"
                            font.pixelSize: 17
                            font.bold: true
                            color: clrTxt
                            font.letterSpacing: 0.3
                        }

                        Rectangle {
                            implicitWidth: badgeRow.implicitWidth + 12
                            implicitHeight: Theme.heightBadge
                            radius: Theme.radiusBadge
                            color: Theme.accentSubtle
                            border.color: Theme.accentBorder
                            border.width: 1

                            RowLayout {
                                id: badgeRow
                                anchors.centerIn: parent
                                spacing: 5

                                Rectangle {
                                    width: 5
                                    height: 5
                                    radius: 2.5
                                    color: clrAccent
                                }

                                Text {
                                    text: "v" + (appBackend ? appBackend.version : "0.1.0")
                                    font.pixelSize: 10
                                    font.bold: true
                                    color: clrAccent
                                }
                            }
                        }
                    }
                }

                Item { height: 6 }
                Rectangle { Layout.fillWidth: true; height: 1; color: clrCardBorder; opacity: 0.8 }
                Item { height: 4 }

                component NavButton: Button {
                    id: navBtn
                    property int targetIndex: 0
                    property string iconGlyph: ""
                    property string labelText: ""

                    Layout.fillWidth: true
                    Layout.preferredHeight: 44
                    scale: down ? 0.97 : 1.0
                    Behavior on scale { NumberAnimation { duration: 120 } }
                    onClicked: navIndex = targetIndex

                    background: Rectangle {
                        radius: Theme.radiusControl
                        color: {
                            if (navIndex === targetIndex) return Theme.accentSubtle;
                            return navBtn.hovered ? Theme.surfaceHover : "transparent";
                        }
                        border.color: {
                            if (navIndex === targetIndex && Theme.isNeon) return Theme.accentSolid;
                            return "transparent";
                        }
                        border.width: (navIndex === targetIndex && Theme.isNeon) ? 1.5 : 0
                        Behavior on color { ColorAnimation { duration: 140 } }
                        Behavior on border.color { ColorAnimation { duration: 140 } }

                        Rectangle {
                            anchors.left: parent.left
                            anchors.leftMargin: 4
                            anchors.verticalCenter: parent.verticalCenter
                            width: 3
                            height: navIndex === targetIndex ? 20 : 0
                            radius: 1.5
                            color: Theme.accentSolid
                            opacity: navIndex === targetIndex ? 1.0 : 0.0
                            Behavior on height { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }
                            Behavior on opacity { NumberAnimation { duration: 140 } }
                        }
                    }

                    contentItem: RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 14
                        anchors.rightMargin: 12
                        spacing: 12
                        transform: Translate {
                            x: (navBtn.hovered && navIndex !== targetIndex) ? 4 : 0
                            Behavior on x { NumberAnimation { duration: 140; easing.type: Easing.OutCubic } }
                        }

                        Icon {
                            glyph: navBtn.iconGlyph
                            size: 18
                            color: navIndex === targetIndex ? (Theme.isDark ? Theme.accentHover : Theme.accentSolid) : (navBtn.hovered ? clrTxt : clrTxt2)
                            scale: navIndex === targetIndex ? 1.15 : 1.0
                            Behavior on scale { NumberAnimation { duration: 140 } }
                            Behavior on color { ColorAnimation { duration: 140 } }
                        }

                        Label {
                            Layout.fillWidth: true
                            text: labelText
                            font.pixelSize: 13
                            font.weight: navIndex === targetIndex ? Font.DemiBold : Font.Normal
                            color: navIndex === targetIndex ? Theme.textPrimary : (navBtn.hovered ? clrTxt : clrTxt2)
                            Behavior on color { ColorAnimation { duration: 140 } }
                        }
                    }
                }

                // Menü Öğeleri (Vektörel Lucide İkonları)
                NavButton {
                    targetIndex: 0
                    iconGlyph: Icons.layoutDashboard
                    labelText: window.t("nav.dashboard")
                }

                NavButton {
                    targetIndex: 1
                    iconGlyph: Icons.wrench
                    labelText: window.t("nav.toolbox")
                }

                NavButton {
                    targetIndex: 2
                    iconGlyph: Icons.settings
                    labelText: window.t("nav.settings")
                }

                NavButton {
                    targetIndex: 3
                    iconGlyph: Icons.terminal
                    labelText: window.t("nav.console")
                }

                NavButton {
                    targetIndex: 4
                    iconGlyph: Icons.squarePen
                    labelText: window.t("nav.editor")
                }

                Item { Layout.fillHeight: true }

                Rectangle { Layout.fillWidth: true; height: 1; color: clrCardBorder; opacity: 0.6 }

                NavButton {
                    targetIndex: 5
                    iconGlyph: Icons.info
                    labelText: window.t("nav.about")
                }

                Button {
                    id: btnPatreonSupport
                    // Warm pink instead of the error red: this is an invitation, not an alarm.
                    readonly property color supportColor: "#F472B6"
                    Layout.fillWidth: true
                    Layout.preferredHeight: 48
                    topInset: 0
                    bottomInset: 0
                    leftInset: 0
                    rightInset: 0
                    // The Material style pads left and right unevenly unless each side is set.
                    padding: 0
                    leftPadding: 0
                    rightPadding: 0
                    topPadding: 0
                    bottomPadding: 0
                    scale: down ? 0.96 : (hovered ? 1.02 : 1.0)
                    transformOrigin: Item.Center
                    Behavior on scale { NumberAnimation { duration: 140; easing.type: Easing.OutCubic } }
                    onClicked: Qt.openUrlExternally("https://www.patreon.com/cw/LordOfTurk")

                    background: Rectangle {
                        radius: Theme.radiusControl
                        color: Qt.rgba(244/255, 114/255, 182/255, btnPatreonSupport.down ? 0.22 : (btnPatreonSupport.hovered ? 0.14 : 0.06))
                        border.color: Qt.rgba(244/255, 114/255, 182/255, btnPatreonSupport.hovered ? 0.9 : 0.4)
                        border.width: 1
                        Behavior on color { ColorAnimation { duration: 150 } }
                        Behavior on border.color { ColorAnimation { duration: 150 } }
                    }

                    // One group centred as a whole: its width is exactly icon + gap + text, so no
                    // spare column width shifts it sideways.
                    contentItem: Item {
                        Row {
                            id: supportRow
                            anchors.centerIn: parent
                            spacing: 10
                            Icon {
                                id: supportHeart
                                glyph: Icons.heart
                                size: 18
                                color: btnPatreonSupport.supportColor
                                anchors.verticalCenter: parent.verticalCenter
                                // A slow heartbeat; it quickens while the pointer is over the button.
                                SequentialAnimation on scale {
                                    loops: Animation.Infinite
                                    running: window.visible
                                    NumberAnimation { to: 1.18; duration: btnPatreonSupport.hovered ? 280 : 620; easing.type: Easing.OutQuad }
                                    NumberAnimation { to: 1.0; duration: btnPatreonSupport.hovered ? 280 : 620; easing.type: Easing.InQuad }
                                    PauseAnimation { duration: btnPatreonSupport.hovered ? 0 : 900 }
                                }
                            }
                            Column {
                                anchors.verticalCenter: parent.verticalCenter
                                Label {
                                    width: Math.min(implicitWidth, 150)
                                    text: window.t("nav.patreon_support")
                                    color: btnPatreonSupport.hovered ? clrTxt : btnPatreonSupport.supportColor
                                    font.pixelSize: 12
                                    font.bold: true
                                    elide: Text.ElideRight
                                    Behavior on color { ColorAnimation { duration: 150 } }
                                }
                                Label {
                                    width: Math.min(implicitWidth, 150)
                                    text: window.t("nav.patreon_sub")
                                    color: clrTxtDim
                                    font.pixelSize: 10
                                    elide: Text.ElideRight
                                }
                            }
                        }
                    }
                }
            }
        }

        // ════════════════════════════════════════════════════════════════════
        // 2. SAĞ İÇERİK ALANI (STACK LAYOUT)
        // ════════════════════════════════════════════════════════════════════
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: clrBg

            StackLayout {
                id: stackLayout
                anchors.fill: parent
                currentIndex: navIndex

                DashboardView {
                    id: dashboardView
                    onOpenEditorRequested: navIndex = 4
                }

                ToolboxView {
                    id: toolboxView
                }

                SettingsView {
                    id: settingsView
                }

                ConsoleView {
                    id: consoleView
                }

                EditorView {
                    id: editorView
                }

                AboutView {
                    id: aboutView
                }
            }
        }
    }

    ToastNotification {
        id: toastNotification
        z: 9999
    }

    Connections {
        target: editorBackend
        function onToastRequested(message, type) {
            toastNotification.show(message, type);
        }
    }

    Connections {
        target: appBackend
        function onToastRequested(message, type) {
            toastNotification.show(message, type);
        }
    }
}
