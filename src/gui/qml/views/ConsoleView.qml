import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import QtQuick.Layouts

Item {
    id: root

    readonly property color clrBg:         "#0B0F17"
    readonly property color clrCard:       "#151A29"
    readonly property color clrCardHover:  "#1D2436"
    readonly property color clrCardBorder: "#242C44"
    readonly property color clrInput:      "#0E121D"
    readonly property color clrAccent:     "#00F2FE"
    readonly property color clrWarn:       "#F59E0B"
    readonly property color clrError:      "#EF4444"
    readonly property color clrSuccess:    "#10B981"
    readonly property color clrTxt:        "#F3F4F6"
    readonly property color clrTxt2:       "#9CA3AF"
    readonly property color clrTxtDim:     "#6B7280"

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
                color: Qt.rgba(0, 242/255, 254/255, 0.12)
                border.color: Qt.rgba(0, 242/255, 254/255, 0.3); border.width: 1
                Label { anchors.centerIn: parent; text: "📜"; font.pixelSize: 18 }
            }

            ColumnLayout {
                spacing: 2
                Label {
                    text: root.t("console.title")
                    font.pixelSize: 20
                    font.bold: true
                    color: clrTxt
                }
                Label {
                    property int logCount: (appBackend && appBackend.logs ? appBackend.logs.length : 0)
                    text: root.t("console.subtitle").replace("{count}", logCount)
                    font.pixelSize: 12
                    color: clrTxt2
                }
            }

            Item { Layout.fillWidth: true }

            Button {
                height: 36
                text: "📋 " + root.t("console.copy_logs_btn")
                scale: down ? 0.97 : (hovered ? 1.02 : 1.0)
                Behavior on scale { NumberAnimation { duration: 100 } }
                background: Rectangle {
                    radius: 8
                    color: parent.hovered ? clrCardHover : clrInput
                    border.color: clrCardBorder; border.width: 1
                }
                contentItem: Label {
                    text: parent.text
                    color: clrTxt
                    font.pixelSize: 12
                    font.bold: true
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                onClicked: appBackend.copyLogs()
            }

            Button {
                height: 36
                text: "🗑️ " + root.t("console.clear_logs_btn")
                scale: down ? 0.97 : (hovered ? 1.02 : 1.0)
                Behavior on scale { NumberAnimation { duration: 100 } }
                background: Rectangle {
                    radius: 8
                    color: parent.hovered ? "#3B1111" : clrInput
                    border.color: clrCardBorder; border.width: 1
                }
                contentItem: Label {
                    text: parent.text
                    color: clrError
                    font.pixelSize: 12
                    font.bold: true
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
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
                height: 36; radius: 8
                color: clrCard; border.color: clrCardBorder; border.width: 1
                Layout.preferredWidth: filterRow.implicitWidth + 8

                RowLayout {
                    id: filterRow
                    anchors.centerIn: parent
                    spacing: 4

                    Repeater {
                        model: [
                            { label: root.t("console.filter_all"), key: "ALL", color: clrTxt },
                            { label: root.t("console.filter_info"), key: "INFO", color: clrAccent },
                            { label: root.t("console.filter_success"), key: "SUCCESS", color: clrSuccess },
                            { label: root.t("console.filter_warn"), key: "WARNING", color: clrWarn },
                            { label: root.t("console.filter_error"), key: "ERROR", color: clrError }
                        ]
                        delegate: Rectangle {
                            width: 68; height: 28; radius: 6
                            color: root.selectedLevel === modelData.key ? Qt.rgba(modelData.color.r, modelData.color.g, modelData.color.b, 0.2) : "transparent"
                            border.color: root.selectedLevel === modelData.key ? modelData.color : "transparent"; border.width: 1

                            Label {
                                anchors.centerIn: parent
                                text: modelData.label
                                font.pixelSize: 10
                                font.bold: root.selectedLevel === modelData.key
                                color: root.selectedLevel === modelData.key ? modelData.color : clrTxt2
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
                height: 36
                radius: 8
                color: clrInput
                border.color: searchInput.activeFocus ? clrAccent : clrCardBorder
                border.width: 1

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 12; anchors.rightMargin: 12
                    spacing: 8

                    Label { text: "🔍"; font.pixelSize: 12; color: clrTxtDim }

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
            radius: 12
            color: "#080C13"
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
                                if (l === "error") return Qt.rgba(239/255, 68/255, 68/255, 0.2);
                                if (l === "warning" || l === "warn") return Qt.rgba(245/255, 158/255, 11/255, 0.2);
                                if (l === "success") return Qt.rgba(16/255, 185/255, 129/255, 0.2);
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
                                font.pixelSize: 9
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
