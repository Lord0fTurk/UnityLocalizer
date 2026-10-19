import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import QtQuick.Layouts

ScrollView {
    id: root
    contentWidth: availableWidth
    clip: true

    readonly property color clrBg:         "#0B0F17"
    readonly property color clrCard:       "#151A29"
    readonly property color clrCardHover:  "#1D2436"
    readonly property color clrCardBorder: "#242C44"
    readonly property color clrAccent:     "#00F2FE"
    readonly property color clrPurple:     "#A855F7"
    readonly property color clrTxt:        "#F3F4F6"
    readonly property color clrTxt2:       "#9CA3AF"
    readonly property color clrTxtDim:     "#6B7280"

    function t(key) {
        return (localeManager && localeManager.currentLanguage, localeManager ? localeManager.t(key) : "");
    }

    Column {
        width: Math.min(parent.width - 48, 860)
        anchors.horizontalCenter: parent.horizontalCenter
        spacing: 24
        topPadding: 32
        bottomPadding: 40

        // App Hero Banner
        Column {
            anchors.horizontalCenter: parent.horizontalCenter
            spacing: 10

            Rectangle {
                width: 64; height: 64; radius: 32
                anchors.horizontalCenter: parent.horizontalCenter
                color: Qt.rgba(0, 242/255, 254/255, 0.12)
                border.color: Qt.rgba(0, 242/255, 254/255, 0.3); border.width: 1
                Label {
                    anchors.centerIn: parent
                    text: "🎮"
                    font.pixelSize: 32
                }
            }

            Label {
                text: "UnityLocalizer"
                font.pixelSize: 28
                font.bold: true
                color: clrTxt
                anchors.horizontalCenter: parent.horizontalCenter
            }

            // Version Pill Badge
            Rectangle {
                anchors.horizontalCenter: parent.horizontalCenter
                implicitWidth: versionLayout.implicitWidth + 20
                implicitHeight: 24
                radius: 12
                color: Qt.rgba(0, 242/255, 254/255, 0.1)
                border.color: Qt.rgba(0, 242/255, 254/255, 0.3); border.width: 1

                RowLayout {
                    id: versionLayout
                    anchors.centerIn: parent
                    spacing: 6

                    Rectangle { width: 6; height: 6; radius: 3; color: clrAccent }
                    Label {
                        property string ver: appBackend ? appBackend.version : "0.1.0"
                        text: root.t("about.edition").replace("{version}", ver)
                        font.pixelSize: 11
                        font.bold: true
                        color: clrAccent
                    }
                }
            }

            Label {
                text: root.t("about.tagline")
                font.pixelSize: 14
                color: clrTxt2
                anchors.horizontalCenter: parent.horizontalCenter
            }
        }

        // Info Card
        Rectangle {
            width: parent.width
            implicitHeight: descCol.implicitHeight + 36
            radius: 14
            color: clrCard
            border.color: clrCardBorder
            border.width: 1

            ColumnLayout {
                id: descCol
                anchors.top: parent.top
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.margins: 20
                spacing: 16

                Label {
                    text: "📖 " + root.t("about.card_title")
                    font.pixelSize: 17
                    font.bold: true
                    color: clrTxt
                }

                Label {
                    text: root.t("about.description")
                    color: clrTxt2
                    font.pixelSize: 13
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                    lineHeight: 1.4
                }

                Rectangle { Layout.fillWidth: true; height: 1; color: clrCardBorder }

                Label {
                    text: "🛠️ " + root.t("about.tech_title")
                    font.pixelSize: 15
                    font.bold: true
                    color: clrTxt
                }

                Flow {
                    Layout.fillWidth: true
                    spacing: 8

                    Repeater {
                        model: [
                            "Python 3.10+", "PyQt6", "Qt Quick (QML)",
                            "UnityPy", "IL2CPP Metadata", "BepInEx 5/6",
                            "Google Translate", "DeepL", "Google Gemini",
                            "OpenAI GPT-4o", "DeepSeek V3", "Ollama / LM Studio"
                        ]
                        delegate: Rectangle {
                            implicitWidth: techText.implicitWidth + 16
                            implicitHeight: 26
                            radius: 13
                            color: Qt.rgba(139/255, 92/255, 246/255, 0.12)
                            border.color: Qt.rgba(139/255, 92/255, 246/255, 0.4); border.width: 1
                            Label {
                                id: techText
                                anchors.centerIn: parent
                                text: modelData
                                font.pixelSize: 11
                                font.bold: true
                                color: clrPurple
                            }
                        }
                    }
                }

                Rectangle { Layout.fillWidth: true; height: 1; color: clrCardBorder }

                RowLayout {
                    Layout.fillWidth: true
                    Label {
                        text: "⚖️ " + root.t("about.license_label")
                        color: clrTxtDim
                        font.pixelSize: 12
                    }
                    Item { Layout.fillWidth: true }
                    Label {
                        text: root.t("about.open_source")
                        color: clrAccent
                        font.pixelSize: 12
                        font.bold: true
                    }
                }
            }
        }
    }
}
