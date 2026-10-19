import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import QtQuick.Controls.Basic as Basic
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

    readonly property bool hasSession: editorBackend ? editorBackend.hasSession : false

    function tr(key, fallback) {
        return (localeManager && localeManager.currentLanguage, localeManager ? localeManager.t(key, fallback || "") : (fallback || ""));
    }

    function statusColor(status) {
        if (status === "accepted") return clrSuccess;
        if (status === "edited") return clrAccent;
        if (status === "repaired") return "#A855F7";
        if (status === "rejected" || status === "invalid") return clrError;
        if (status === "failed") return clrWarn;
        return clrTxtDim;
    }

    function tint(c, a) {
        return Qt.rgba(c.r, c.g, c.b, a);
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 20
        spacing: 14

        // Header & save action
        RowLayout {
            Layout.fillWidth: true
            spacing: 12

            Rectangle {
                width: 38; height: 38; radius: 10
                color: tint(clrAccent, 0.12)
                border.color: tint(clrAccent, 0.3); border.width: 1
                Label { anchors.centerIn: parent; text: "📝"; font.pixelSize: 18 }
            }

            ColumnLayout {
                spacing: 2
                Label {
                    text: root.tr("editor.title")
                    font.pixelSize: 20
                    font.bold: true
                    color: clrTxt
                }
                Label {
                    text: root.hasSession
                          ? root.tr("editor.subtitle")
                                .replace("{total}", editorBackend.totalCount)
                                .replace("{ready}", editorBackend.shippableCount)
                                .replace("{lang}", editorBackend.targetLanguage)
                          : root.tr("editor.subtitle_empty")
                    font.pixelSize: 12
                    color: clrTxt2
                }
            }

            Item { Layout.fillWidth: true }

            Button {
                height: 36
                enabled: root.hasSession && editorBackend.shippableCount > 0
                opacity: enabled ? 1.0 : 0.45
                text: "💾 " + root.tr("editor.save_btn")
                scale: down ? 0.97 : (hovered ? 1.02 : 1.0)
                Behavior on scale { NumberAnimation { duration: 100 } }
                background: Rectangle {
                    radius: 8
                    color: parent.hovered ? tint(clrSuccess, 0.25) : tint(clrSuccess, 0.15)
                    border.color: clrSuccess; border.width: 1
                }
                contentItem: Label {
                    text: parent.text
                    color: clrSuccess
                    font.pixelSize: 12
                    font.bold: true
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                onClicked: {
                    forceActiveFocus();
                    editorBackend.saveToGame();
                }
            }
        }

        // Status filter chips & search
        RowLayout {
            Layout.fillWidth: true
            spacing: 12
            visible: root.hasSession

            Flow {
                Layout.fillWidth: true
                spacing: 6

                Repeater {
                    model: [
                        { key: "", label: root.tr("editor.filter_all") },
                        { key: "rejected", label: root.tr("editor.status_rejected") },
                        { key: "invalid", label: root.tr("editor.status_invalid") },
                        { key: "failed", label: root.tr("editor.status_failed") },
                        { key: "edited", label: root.tr("editor.status_edited") },
                        { key: "repaired", label: root.tr("editor.status_repaired") },
                        { key: "accepted", label: root.tr("editor.status_accepted") },
                        { key: "unchanged", label: root.tr("editor.status_unchanged") }
                    ]
                    delegate: Rectangle {
                        readonly property bool active: editorBackend && editorBackend.statusFilter === modelData.key
                        readonly property color chipColor: modelData.key === "" ? clrTxt : root.statusColor(modelData.key)
                        readonly property int chipCount: !editorBackend ? 0
                            : (modelData.key === "" ? editorBackend.totalCount : (editorBackend.counts[modelData.key] || 0))
                        height: 28; radius: 6
                        width: chipLabel.implicitWidth + 20
                        color: active ? root.tint(chipColor, 0.2) : clrCard
                        border.color: active ? chipColor : clrCardBorder; border.width: 1

                        Label {
                            id: chipLabel
                            anchors.centerIn: parent
                            text: modelData.label + " (" + chipCount + ")"
                            font.pixelSize: 11
                            font.bold: active
                            color: active ? chipColor : clrTxt2
                        }

                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: editorBackend.setStatusFilter(modelData.key)
                        }
                    }
                }
            }

            Rectangle {
                Layout.preferredWidth: 280
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
                        onTextChanged: editorBackend.setFilterQuery(text)

                        Text {
                            anchors.fill: parent
                            text: root.tr("editor.search_placeholder")
                            color: clrTxtDim
                            font.pixelSize: 12
                            visible: !searchInput.text && !searchInput.activeFocus
                            verticalAlignment: Text.AlignVCenter
                        }
                    }
                }
            }
        }

        Label {
            Layout.fillWidth: true
            visible: root.hasSession && editorBackend.matchCount > editorBackend.maxVisibleRows
            text: root.tr("editor.cap_notice")
                    .replace("{total}", editorBackend ? editorBackend.matchCount : 0)
                    .replace("{shown}", editorBackend ? editorBackend.maxVisibleRows : 0)
            font.pixelSize: 11
            color: clrWarn
        }

        // Rows
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            radius: 12
            color: "#080C13"
            border.color: clrCardBorder
            border.width: 1

            Label {
                anchors.centerIn: parent
                width: parent.width * 0.7
                visible: !root.hasSession || editorBackend.matchCount === 0
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
                text: !root.hasSession
                      ? root.tr("editor.empty")
                      : root.tr("editor.no_matches")
                font.pixelSize: 13
                color: clrTxt2
            }

            ListView {
                id: rowList
                anchors.fill: parent
                anchors.margins: 10
                clip: true
                spacing: 8
                visible: root.hasSession
                model: editorBackend ? editorBackend.filteredRows : []
                ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                delegate: Rectangle {
                    width: rowList.width - 12
                    implicitHeight: rowCol.implicitHeight + 20
                    radius: 8
                    color: clrCard
                    border.color: root.tint(root.statusColor(modelData.status), 0.45)
                    border.width: 1

                    ColumnLayout {
                        id: rowCol
                        anchors.fill: parent
                        anchors.margins: 10
                        spacing: 6

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8

                            Rectangle {
                                implicitWidth: statusLabel.implicitWidth + 14; implicitHeight: 20; radius: 4
                                color: root.tint(root.statusColor(modelData.status), 0.18)
                                border.color: root.statusColor(modelData.status); border.width: 1
                                Label {
                                    id: statusLabel
                                    anchors.centerIn: parent
                                    text: root.tr("editor.status_" + modelData.status, modelData.status)
                                    font.pixelSize: 10
                                    font.bold: true
                                    color: root.statusColor(modelData.status)
                                }
                            }

                            TextEdit {
                                Layout.fillWidth: true
                                readOnly: true
                                selectByMouse: true
                                wrapMode: TextEdit.Wrap
                                text: modelData.original
                                font.pixelSize: 12
                                color: clrTxt2
                            }
                        }

                        // Basic style: Material's floating label and insets fight the custom background.
                        Basic.TextArea {
                            id: translationInput
                            Layout.fillWidth: true
                            Layout.preferredHeight: Math.max(38, contentHeight + topPadding + bottomPadding)
                            padding: 9
                            text: modelData.translation
                            wrapMode: TextEdit.Wrap
                            selectByMouse: true
                            font.pixelSize: 13
                            color: clrTxt
                            selectionColor: root.tint(clrAccent, 0.35)
                            horizontalAlignment: editorBackend && editorBackend.isRtl ? Text.AlignRight : Text.AlignLeft
                            placeholderText: root.tr("editor.translation_placeholder")
                            placeholderTextColor: clrTxtDim
                            background: Rectangle {
                                radius: 6
                                color: clrInput
                                border.color: translationInput.activeFocus ? clrAccent : clrCardBorder
                                border.width: 1
                            }
                            function commitEdit() {
                                if (!editorBackend || text === modelData.translation) return;
                                var savedY = rowList.contentY;
                                editorBackend.updateTranslation(modelData.id, text);
                                Qt.callLater(function() { rowList.contentY = savedY; });
                            }
                            onEditingFinished: commitEdit()
                            onActiveFocusChanged: { if (!activeFocus) commitEdit(); }
                        }

                        Label {
                            Layout.fillWidth: true
                            visible: modelData.errors.length > 0
                            wrapMode: Text.WordWrap
                            text: "⚠️ " + modelData.errors
                            font.pixelSize: 11
                            color: clrError
                        }
                    }
                }
            }
        }
    }
}
