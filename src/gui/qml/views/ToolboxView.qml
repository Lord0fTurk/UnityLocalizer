import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import QtQuick.Layouts

ScrollView {
    id: root
    contentWidth: availableWidth
    clip: true

    readonly property color clrCard:       "#151A29"
    readonly property color clrCardHover:  "#1D2436"
    readonly property color clrCardBorder: "#242C44"
    readonly property color clrAccent:     "#8B5CF6"
    readonly property color clrAccentCyan: "#00F2FE"
    readonly property color clrTxt:        "#F3F4F6"
    readonly property color clrTxt2:       "#9CA3AF"

    function t(key) {
        return (localeManager && localeManager.currentLanguage, localeManager ? localeManager.t(key) : "");
    }

    Column {
        width: Math.min(parent.width - 48, 920)
        anchors.horizontalCenter: parent.horizontalCenter
        spacing: 20
        topPadding: 24
        bottomPadding: 40

        // Header
        Column {
            spacing: 6
            Text {
                text: "🛠️ " + root.t("toolbox.title")
                font.pixelSize: 26
                font.bold: true
                color: clrTxt
            }
            Text {
                text: root.t("toolbox.subtitle")
                font.pixelSize: 13
                color: clrTxt2
            }
        }

        // Card 1: TextMeshPro Font Fixer
        Rectangle {
            width: parent.width
            implicitHeight: fontCol.implicitHeight + 36
            radius: 14
            color: clrCard
            border.color: clrCardBorder
            border.width: 1

            Column {
                id: fontCol
                anchors.top: parent.top
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.margins: 18
                spacing: 12

                RowLayout {
                    width: parent.width
                    Text {
                        text: "🔡 " + root.t("toolbox.font_card_title")
                        font.pixelSize: 16
                        font.bold: true
                        color: clrTxt
                    }
                    Item { Layout.fillWidth: true }
                    Rectangle {
                        implicitWidth: 100; implicitHeight: 22; radius: 11
                        color: Qt.rgba(16/255, 185/255, 129/255, 0.12)
                        border.color: Qt.rgba(16/255, 185/255, 129/255, 0.4)
                        Text {
                            anchors.centerIn: parent
                            text: root.t("toolbox.font_recommended_badge")
                            font.pixelSize: 11; font.bold: true; color: "#10B981"
                        }
                    }
                }

                Text {
                    text: root.t("toolbox.font_desc")
                    font.pixelSize: 13
                    color: clrTxt2
                    wrapMode: Text.WordWrap
                    width: parent.width
                    lineHeight: 1.3
                }

                Button {
                    text: "✨ " + root.t("toolbox.inject_font_btn")
                    Material.background: "#10B981"
                    enabled: Boolean(appBackend && appBackend.gamePath && !appBackend.isBusy)
                    scale: down ? 0.97 : (hovered ? 1.02 : 1.0)
                    Behavior on scale { NumberAnimation { duration: 120 } }
                    onClicked: {
                        if (appBackend) appBackend.injectFont();
                    }
                }
            }
        }

        // Card 2: BepInEx Modding
        Rectangle {
            width: parent.width
            implicitHeight: bepCol.implicitHeight + 36
            radius: 14
            color: clrCard
            border.color: clrCardBorder
            border.width: 1

            Column {
                id: bepCol
                anchors.top: parent.top
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.margins: 18
                spacing: 12

                RowLayout {
                    width: parent.width
                    Text {
                        text: "🪝 " + root.t("toolbox.bepinex_card_title")
                        font.pixelSize: 16
                        font.bold: true
                        color: clrTxt
                    }
                    Item { Layout.fillWidth: true }
                    Rectangle {
                        implicitWidth: hookStatusTxt.implicitWidth + 16
                        implicitHeight: 24
                        radius: 12
                        color: (appBackend && appBackend.hasBepInEx) ? Qt.rgba(16/255, 185/255, 129/255, 0.15) : Qt.rgba(245/255, 158/255, 11/255, 0.15)
                        border.color: (appBackend && appBackend.hasBepInEx) ? "#10B981" : "#F59E0B"
                        border.width: 1
                        Text {
                            id: hookStatusTxt
                            anchors.centerIn: parent
                            text: (appBackend && appBackend.hasBepInEx)
                                  ? root.t("dashboard.bepinex_active")
                                  : root.t("dashboard.vanilla")
                            font.pixelSize: 11
                            font.bold: true
                            color: (appBackend && appBackend.hasBepInEx) ? "#10B981" : "#F59E0B"
                        }
                    }
                }

                Text {
                    text: root.t("toolbox.bepinex_desc")
                    font.pixelSize: 13
                    color: clrTxt2
                    wrapMode: Text.WordWrap
                    width: parent.width
                    lineHeight: 1.3
                }

                Row {
                    spacing: 12

                    Button {
                        text: "📦 " + root.t("toolbox.install_hooks_btn")
                        Material.background: clrAccent
                        enabled: Boolean(appBackend && appBackend.gamePath && !appBackend.isBusy)
                        scale: down ? 0.97 : (hovered ? 1.02 : 1.0)
                        Behavior on scale { NumberAnimation { duration: 120 } }
                        onClicked: {
                            if (appBackend) {
                                appBackend.installHooks();
                            }
                        }
                    }

                    Button {
                        text: "🗑️ " + root.t("toolbox.uninstall_bepinex_btn")
                        Material.background: "#EF4444"
                        enabled: Boolean(appBackend && appBackend.gamePath && !appBackend.isBusy && appBackend.hasBepInEx)
                        scale: down ? 0.97 : (hovered ? 1.02 : 1.0)
                        Behavior on scale { NumberAnimation { duration: 120 } }
                        onClicked: {
                            if (appBackend) appBackend.uninstallHooks();
                        }
                    }
                }
            }
        }

        // Card 3: Static Binary & Asset Harvester
        Rectangle {
            width: parent.width
            implicitHeight: harvCol.implicitHeight + 36
            radius: 14
            color: clrCard
            border.color: clrCardBorder
            border.width: 1

            Column {
                id: harvCol
                anchors.top: parent.top
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.margins: 18
                spacing: 14

                RowLayout {
                    width: parent.width
                    Text {
                        text: "⛏️ " + root.t("toolbox.harvester_card_title")
                        font.pixelSize: 16
                        font.bold: true
                        color: clrTxt
                    }
                    Item { Layout.fillWidth: true }
                    Rectangle {
                        implicitWidth: harvestBadge.implicitWidth + 16; implicitHeight: 24; radius: 12
                        color: Qt.rgba(139/255, 92/255, 246/255, 0.15)
                        border.color: Qt.rgba(139/255, 92/255, 246/255, 0.5)
                        Text {
                            id: harvestBadge
                            anchors.centerIn: parent
                            text: root.t("toolbox.harvester_badge").replace("{count}", appBackend ? appBackend.harvestCount : 0)
                            font.pixelSize: 11; font.bold: true; color: clrAccent
                        }
                    }
                }

                Text {
                    text: root.t("toolbox.harvester_desc")
                    font.pixelSize: 13
                    color: clrTxt2
                    wrapMode: Text.WordWrap
                    width: parent.width
                    lineHeight: 1.3
                }

                Flow {
                    width: parent.width
                    spacing: 12

                    Button {
                        text: "🔍 " + root.t("toolbox.harvest_metadata_btn")
                        Material.background: "#252D42"
                        enabled: Boolean(appBackend && appBackend.gamePath && !appBackend.isBusy)
                        scale: down ? 0.97 : (hovered ? 1.02 : 1.0)
                        Behavior on scale { NumberAnimation { duration: 120 } }
                        onClicked: {
                            if (appBackend) appBackend.harvestMetadata();
                        }
                    }

                    Button {
                        text: "⚙️ " + root.t("toolbox.harvest_assembly_btn")
                        Material.background: "#252D42"
                        enabled: Boolean(appBackend && appBackend.gamePath && !appBackend.isBusy)
                        scale: down ? 0.97 : (hovered ? 1.02 : 1.0)
                        Behavior on scale { NumberAnimation { duration: 120 } }
                        onClicked: {
                            if (appBackend) appBackend.harvestAssembly();
                        }
                    }

                    Button {
                        text: "📂 " + root.t("toolbox.harvest_streaming_btn")
                        Material.background: "#252D42"
                        enabled: Boolean(appBackend && appBackend.gamePath && !appBackend.isBusy)
                        scale: down ? 0.97 : (hovered ? 1.02 : 1.0)
                        Behavior on scale { NumberAnimation { duration: 120 } }
                        onClicked: {
                            if (appBackend) appBackend.harvestStreamingAssets();
                        }
                    }

                    Button {
                        text: root.t("toolbox.harvest_assets_btn")
                        Material.background: "#252D42"
                        enabled: Boolean(appBackend && appBackend.gamePath && !appBackend.isBusy)
                        scale: down ? 0.97 : (hovered ? 1.02 : 1.0)
                        Behavior on scale { NumberAnimation { duration: 120 } }
                        onClicked: {
                            if (appBackend) appBackend.harvestAssets();
                        }
                    }
                }
            }
        }
    }
}
