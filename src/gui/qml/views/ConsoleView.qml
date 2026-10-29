import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import QtQuick.Layouts
import "../components"

Item {
    id: root

    readonly property color clrBg:         Theme.canvas
    readonly property color clrCard:       Theme.surfaceCard
    readonly property color clrCardHover:  Theme.surfaceHover
    readonly property color clrCardBorder: Theme.borderCard
    readonly property color clrInput:      Theme.surfaceControl
    readonly property color clrAccent:     Theme.accentSolid
    readonly property color clrWarn:       Theme.statusWarning
    readonly property color clrError:      Theme.statusDanger
    readonly property color clrSuccess:    Theme.statusSuccess
    readonly property color clrTxt:        Theme.textPrimary
    readonly property color clrTxt2:       Theme.textSecondary
    readonly property color clrTxtDim:     Theme.textMuted

    property string selectedLevel: "ALL"
    property string searchQuery: ""

    function t(key) {
        return (localeManager && localeManager.currentLanguage, localeManager ? localeManager.t(key) : "");
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 20
        spacing: 14

        // Top Bar: Header & Actions
        RowLayout {
            Layout.fillWidth: true
            spacing: 12

            Rectangle {
                width: 38; height: 38; radius: 10
                color: Theme.accentAlpha(0.12)
                border.color: Theme.accentAlpha(0.3); border.width: 1
                Icon { anchors.centerIn: parent; glyph: Icons.terminal; size: 20; color: Theme.accentSolid }
            }

            ColumnLayout {
                spacing: 2
                Label {
                    text: root.t("console.title")
                    font.pixelSize: 22
                    font.bold: true
                    color: Theme.textPrimary
                }
                Label {
                    property int logCount: (appBackend && appBackend.logs ? appBackend.logs.length : 0)
                    text: root.t("console.subtitle").replace("{count}", logCount)
                    font.pixelSize: 13
                    color: Theme.textSecondary
                }
            }

            Item { Layout.fillWidth: true }

            Button {
                Accessible.name: root.t("console.copy_logs_btn")
                height: Theme.heightSecondary
                topInset: 0; bottomInset: 0; leftInset: 0; rightInset: 0; padding: 0
                scale: down ? 0.97 : (hovered ? 1.02 : 1.0)
                Behavior on scale { NumberAnimation { duration: 100 } }
                background: Rectangle {
                    radius: Theme.radiusControl
                    color: parent.hovered ? Theme.surfaceHover : Theme.surfaceControl
                    border.color: parent.hovered ? Theme.borderFocus : Theme.borderControl
                    border.width: 1
                }
                contentItem: RowLayout {
                    spacing: 6
                    anchors.centerIn: parent
                    Icon { glyph: Icons.copy; size: 14; color: Theme.textPrimary }
                    Label {
                        text: root.t("console.copy_logs_btn")
                        color: Theme.textPrimary
                        font.pixelSize: 13
                        font.bold: true
                    }
                }
                onClicked: appBackend.copyLogs()
            }

            Button {
                Accessible.name: root.t("console.clear_logs_btn")
                height: Theme.heightSecondary
                topInset: 0; bottomInset: 0; leftInset: 0; rightInset: 0; padding: 0
                scale: down ? 0.97 : (hovered ? 1.02 : 1.0)
                Behavior on scale { NumberAnimation { duration: 100 } }
                background: Rectangle {
                    radius: Theme.radiusControl
                    color: parent.hovered ? Theme.statusDangerSubtle : Theme.surfaceControl
                    border.color: parent.hovered ? Theme.statusDanger : Theme.statusDangerBorder
                    border.width: 1
                }
                contentItem: RowLayout {
                    spacing: 6
                    anchors.centerIn: parent
                    Icon { glyph: Icons.trash2; size: 14; color: Theme.statusDanger }
                    Label {
                        text: root.t("console.clear_logs_btn")
                        color: Theme.statusDanger
                        font.pixelSize: 13
                        font.bold: true
                    }
                }
                onClicked: appBackend.clearLogs()
            }
        }

        // Filter & Search Controls
        RowLayout {
            Layout.fillWidth: true
            spacing: 12

            // Level Buttons
            Rectangle {
                height: Theme.heightSecondary; radius: Theme.radiusControl
                color: Theme.surfaceCard; border.color: Theme.borderCard; border.width: 1
                Layout.preferredWidth: filterRow.implicitWidth + 8

                RowLayout {
                    id: filterRow
                    anchors.centerIn: parent
                    spacing: 4

                    Repeater {
                        model: [
                            { label: root.t("console.filter_all"), key: "ALL", color: Theme.textPrimary },
                            { label: root.t("console.filter_info"), key: "INFO", color: Theme.accentSolid },
                            { label: root.t("console.filter_success"), key: "SUCCESS", color: Theme.statusSuccess },
                            { label: root.t("console.filter_warn"), key: "WARNING", color: Theme.statusWarning },
                            { label: root.t("console.filter_error"), key: "ERROR", color: Theme.statusDanger }
                        ]
                        delegate: Rectangle {
                            width: 68; height: 28; radius: Theme.radiusBadge
                            color: root.selectedLevel === modelData.key ? Theme.accentSubtle : "transparent"
                            border.color: root.selectedLevel === modelData.key ? Theme.accentBorder : "transparent"; border.width: 1

                            Label {
                                anchors.centerIn: parent
                                text: modelData.label
                                font.pixelSize: 11
                                font.bold: root.selectedLevel === modelData.key
                                color: root.selectedLevel === modelData.key ? modelData.color : Theme.textSecondary
                            }

                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.selectedLevel = modelData.key
                            }
                        }
                    }
                }
            }

            // Search Bar
            Rectangle {
                Layout.fillWidth: true
                height: Theme.heightInput
                radius: Theme.radiusControl
                color: Theme.surfaceControl
                border.color: searchInput.activeFocus ? Theme.borderFocus : Theme.borderControl
                border.width: 1

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 12; anchors.rightMargin: 12
                    spacing: 8

                    Icon { glyph: Icons.search; size: 14; color: clrTxtDim }

                    TextInput {
                        id: searchInput
                        Layout.fillWidth: true
                        font.pixelSize: 12
                        color: clrTxt
                        clip: true
                        onTextChanged: root.searchQuery = text.toLowerCase()

                        Text {
                            anchors.fill: parent
                            text: root.t("console.search_placeholder")
                            color: clrTxtDim
                            font.pixelSize: 12
                            visible: !searchInput.text && !searchInput.activeFocus
                            verticalAlignment: Text.AlignVCenter
                        }
                    }
                }
            }
        }

        // Terminal Output Screen
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            radius: Theme.radiusCard
            color: Theme.surfaceInset
            border.color: clrCardBorder
            border.width: 1

            ListView {
                id: logList
                anchors.fill: parent
                anchors.margins: 10
                clip: true
                spacing: 4
                model: appBackend ? appBackend.logs : []

                delegate: Rectangle {
                    width: logList.width
                    implicitHeight: logRow.implicitHeight + 8
                    radius: 6
                    color: index % 2 === 0 ? "transparent" : Qt.rgba(1, 1, 1, 0.02)

                    visible: {
                        var lvl = (modelData.level || "").toUpperCase();
                        if (root.selectedLevel !== "ALL") {
                            if (root.selectedLevel === "INFO" && lvl !== "INFO") return false;
                            if (root.selectedLevel === "SUCCESS" && lvl !== "SUCCESS") return false;
                            if (root.selectedLevel === "WARNING" && (lvl !== "WARNING" && lvl !== "WARN")) return false;
                            if (root.selectedLevel === "ERROR" && lvl !== "ERROR") return false;
                        }
                        if (root.searchQuery.length > 0) {
                            var msg = (modelData.message || "").toLowerCase();
                            return msg.indexOf(root.searchQuery) >= 0;
                        }
                        return true
                    }

                    RowLayout {
                        id: logRow
                        anchors.fill: parent
                        anchors.leftMargin: 8; anchors.rightMargin: 8
                        spacing: 10

                        // Timestamp
                        Label {
                            text: modelData.ts || "00:00:00"
                            font.family: "Consolas, 'Cascadia Code', monospace"
                            font.pixelSize: 11
                            color: clrTxtDim
                        }

                        // Level Badge
                        Rectangle {
                            implicitWidth: 64; implicitHeight: 18; radius: 4
                            color: {
                                var l = (modelData.level || "").toLowerCase();
                                if (l === "error") return Qt.alpha(Theme.statusDanger, 0.2);
                                if (l === "warning" || l === "warn") return Qt.alpha(Theme.statusWarning, 0.2);
                                if (l === "success") return Qt.alpha(Theme.statusSuccess, 0.2);
                                return Qt.rgba(0, 242/255, 254/255, 0.15);
                            }
                            border.color: {
                                var l = (modelData.level || "").toLowerCase();
                                if (l === "error") return clrError;
                                if (l === "warning" || l === "warn") return clrWarn;
                                if (l === "success") return clrSuccess;
                                return clrAccent;
                            }
                            border.width: 1

                            Label {
                                anchors.centerIn: parent
                                text: {
                                    // Same localized labels as the level filter chips above.
                                    var l = (modelData.level || "info").toLowerCase();
                                    var key = l === "warning" ? "warn" : l;
                                    return root.t("console.filter_" + key);
                                }
                                font.pixelSize: 11
                                font.bold: true
                                color: {
                                    var l = (modelData.level || "").toLowerCase();
                                    if (l === "error") return clrError;
                                    if (l === "warning" || l === "warn") return clrWarn;
                                    if (l === "success") return clrSuccess;
                                    return clrAccent;
                                }
                            }
                        }

                        // Message Content
                        Label {
                            Layout.fillWidth: true
                            text: modelData.message || ""
                            font.family: "Consolas, 'Cascadia Code', monospace"
                            font.pixelSize: 12
                            color: clrTxt
                            wrapMode: Text.WordWrap
                        }
                    }
                }

                ScrollBar.vertical: ScrollBar {
                    active: true
                }

                onCountChanged: {
                    Qt.callLater(function() {
                        logList.positionViewAtEnd();
                    });
                }
            }
        }
    }
}
