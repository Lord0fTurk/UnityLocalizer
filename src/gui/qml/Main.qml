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
    color: clrBg

    Material.theme: Material.Dark
    Material.accent: clrAccent

    // ── Tek Premium Siberpunk & Glassmorphism Renk Paleti (RenLocalizer Paritesi) ──
    readonly property color clrBg:         "#0B0F17"
    readonly property color clrSidebar:    "#111522"
    readonly property color clrSidebarTop: "#161B2E"
    readonly property color clrCard:       "#151A29"
    readonly property color clrCardHover:  "#1D2436"
    readonly property color clrCardBorder: "#242C44"
    readonly property color clrBorderGlow: "#00F2FE"
    readonly property color clrInput:      "#0E121D"
    readonly property color clrAccent:     "#00F2FE"
    readonly property color clrAccent2:    "#4FACFE"
    readonly property color clrPurple:     "#A855F7"
    readonly property color clrSuccess:    "#10B981"
    readonly property color clrWarn:       "#F59E0B"
    readonly property color clrError:      "#EF4444"
    readonly property color clrTxt:        "#F3F4F6"
    readonly property color clrTxt2:       "#9CA3AF"
    readonly property color clrTxtDim:     "#6B7280"

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
                        color: Qt.rgba(0, 242/255, 254/255, 0.12)
                        border.color: Qt.rgba(0, 242/255, 254/255, 0.3)
                        border.width: 1

                        Label {
                            anchors.centerIn: parent
                            text: "🎮"
                            font.pixelSize: 22
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
                            implicitHeight: 18
                            radius: 9
                            color: Qt.rgba(0, 242/255, 254/255, 0.08)
                            border.color: Qt.rgba(0, 242/255, 254/255, 0.25)
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
                    property string iconText: ""
                    property string labelText: ""

                    Layout.fillWidth: true
                    Layout.preferredHeight: 44
                    scale: down ? 0.97 : 1.0
                    Behavior on scale { NumberAnimation { duration: 120 } }
                    onClicked: navIndex = targetIndex

                    background: Rectangle {
                        radius: 10
                        color: navIndex === targetIndex ? Qt.rgba(0, 242/255, 254/255, 0.14) : (navBtn.hovered ? clrCardHover : "transparent")
                        border.color: navIndex === targetIndex ? Qt.rgba(0, 242/255, 254/255, 0.6) : "transparent"
                        border.width: 1
                        Behavior on color { ColorAnimation { duration: 140 } }
                        Behavior on border.color { ColorAnimation { duration: 140 } }

                        Rectangle {
                            anchors.left: parent.left
                            anchors.leftMargin: 4
                            anchors.verticalCenter: parent.verticalCenter
                            width: 3
                            height: navIndex === targetIndex ? 22 : 0
                            radius: 1.5
                            color: clrAccent
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

                        Label {
                            text: iconText
                            font.pixelSize: 16
                            scale: navIndex === targetIndex ? 1.15 : 1.0
                            Behavior on scale { NumberAnimation { duration: 140 } }
                        }

                        Label {
                            Layout.fillWidth: true
                            text: labelText
                            font.pixelSize: 13
                            font.bold: navIndex === targetIndex
                            color: navIndex === targetIndex ? clrAccent : clrTxt
                            Behavior on color { ColorAnimation { duration: 140 } }
                        }
                    }
                }

                // Menü Öğeleri (Tamamen i18n dinamik)
                NavButton {
                    targetIndex: 0
                    iconText: "🏠"
                    labelText: window.t("nav.dashboard")
                }

                NavButton {
                    targetIndex: 1
                    iconText: "🧰"
                    labelText: window.t("nav.toolbox")
                }

                NavButton {
                    targetIndex: 2
                    iconText: "⚙️"
                    labelText: window.t("nav.settings")
                }

                NavButton {
                    targetIndex: 3
                    iconText: "📜"
                    labelText: window.t("nav.console")
                }

                NavButton {
                    targetIndex: 4
                    iconText: "📝"
                    labelText: window.t("nav.editor")
                }

                Item { Layout.fillHeight: true }

                Rectangle { Layout.fillWidth: true; height: 1; color: clrCardBorder; opacity: 0.6 }

                NavButton {
                    targetIndex: 5
                    iconText: "ℹ️"
                    labelText: window.t("nav.about")
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
