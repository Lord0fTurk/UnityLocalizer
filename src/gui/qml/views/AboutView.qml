import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import QtQuick.Layouts
import "../components"

ScrollView {
    id: root
    contentWidth: availableWidth
    clip: true

    readonly property color clrBg:         Theme.canvas
    readonly property color clrCard:       Theme.surfaceCard
    readonly property color clrCardHover:  Theme.surfaceHover
    readonly property color clrCardBorder: Theme.borderCard
    readonly property color clrAccent:     Theme.accentSolid
    readonly property color clrPurple:     Theme.isDark ? Theme.accentHover : Theme.accentSolid
    readonly property color clrTxt:        Theme.textPrimary
    readonly property color clrTxt2:       Theme.textSecondary
    readonly property color clrTxtDim:     Theme.textMuted

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
                width: 64; height: 64; radius: 16
                anchors.horizontalCenter: parent.horizontalCenter
                color: Theme.accentAlpha(0.12)
                border.color: Theme.accentAlpha(0.3); border.width: 1
                Image {
                    anchors.fill: parent
                    anchors.margins: 8
                    source: appBackend ? appBackend.get_asset_url("icon.png") : ""
                    sourceSize: Qt.size(64, 64)
                    fillMode: Image.PreserveAspectFit
                    smooth: true
                    mipmap: true
                }
            }

            Label {
                text: "UnityLocalizer"
                font.pixelSize: 28
                font.bold: true
                color: clrTxt
                anchors.horizontalCenter: parent.horizontalCenter
            }

            // Version Pill Badge (DESIGN.md §3.6: radius 4px)
            Rectangle {
                anchors.horizontalCenter: parent.horizontalCenter
                implicitWidth: versionLayout.implicitWidth + 20
                implicitHeight: Theme.heightBadge
                radius: Theme.radiusBadge
                color: Theme.accentSubtle
                border.color: Theme.accentBorder
                border.width: 1

                RowLayout {
                    id: versionLayout
                    anchors.centerIn: parent
                    spacing: 6

                    Rectangle { width: 6; height: 6; radius: 3; color: Theme.accentSolid }
                    Label {
                        property string ver: appBackend ? appBackend.version : "0.1.0"
                        text: root.t("about.edition").replace("{version}", ver)
                        font.pixelSize: 11
                        font.bold: true
                        color: Theme.isDark ? Theme.accentHover : Theme.accentSolid
                    }
                }
            }

            Label {
                text: root.t("about.tagline")
                font.pixelSize: 13
                color: Theme.textSecondary
                anchors.horizontalCenter: parent.horizontalCenter
            }
        }

        // Info Card
        Rectangle {
            width: parent.width
            implicitHeight: descCol.implicitHeight + 36
            radius: Theme.radiusCard
            color: Theme.surfaceCard
            border.color: Theme.borderCard
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
                    font.pixelSize: 15
                    font.bold: true
                    color: Theme.textPrimary
                }

                Label {
                    text: root.t("about.description")
                    color: Theme.textSecondary
                    font.pixelSize: 13
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                    lineHeight: 1.4
                }

                Rectangle { Layout.fillWidth: true; height: 1; color: Theme.borderCard }

                Label {
                    text: "🛠️ " + root.t("about.tech_title")
                    font.pixelSize: 15
                    font.bold: true
                    color: Theme.textPrimary
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
                            implicitHeight: Theme.heightBadge
                            radius: Theme.radiusBadge
                            color: Theme.surfaceControl
                            border.color: Theme.borderControl
                            border.width: 1
                            Label {
                                id: techText
                                anchors.centerIn: parent
                                text: modelData
                                font.pixelSize: 11
                                font.weight: Font.Medium
                                color: Theme.textSecondary
                            }
                        }
                    }
                }

                Rectangle { Layout.fillWidth: true; height: 1; color: Theme.borderCard }

                RowLayout {
                    Layout.fillWidth: true
                    Label {
                        text: "⚖️ " + root.t("about.license_label")
                        color: Theme.textMuted
                        font.pixelSize: 12
                    }
                    Item { Layout.fillWidth: true }
                    Label {
                        text: root.t("about.open_source")
                        color: Theme.accentSolid
                        font.pixelSize: 12
                        font.bold: true
                    }
                }
            }
        }
    }
}
