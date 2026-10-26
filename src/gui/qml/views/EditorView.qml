import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import QtQuick.Controls.Basic as Basic
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

    readonly property bool hasSession: editorBackend ? editorBackend.hasSession : false
    readonly property var selectedRow: editorBackend ? editorBackend.selected : ({})
    readonly property bool hasSelection: selectedRow.id !== undefined

    // With no finished run to review, open the dictionary already in the selected game.
    readonly property string gameKey: appBackend ? appBackend.gamePath + "|" + appBackend.targetLanguage : ""
    function openExisting() {
        if (editorBackend && appBackend && appBackend.gamePath && root.visible)
            editorBackend.loadExisting(appBackend.gamePath, appBackend.targetLanguage, appBackend.sourceLanguage);
    }
    onGameKeyChanged: openExisting()
    onVisibleChanged: openExisting()

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

    // One line for the list: line breaks shown as a return symbol.
    function oneLine(text) {
        return String(text || "").replace(/\r?\n/g, " ↵ ");
    }

    // Keep what was typed in the detail box before anything that moves the selection or the page.
    function commit() {
        if (!hasSelection) return;
        if (transArea.text !== selectedRow.translation)
            editorBackend.updateTranslation(selectedRow.id, transArea.text);
    }

    function selectRow(rowId) {
        commit();
        editorBackend.select(rowId);
    }

    function goPage(page) {
        commit();
        editorBackend.setPage(page);
    }

    // Ctrl+Enter: keep the edit and move to the next line (next page at the end of this one).
    function commitAndNext() {
        commit();
        var rows = editorBackend.filteredRows;
        for (var i = 0; i < rows.length; i++) {
            if (rows[i].id === selectedRow.id) {
                if (i + 1 < rows.length) editorBackend.select(rows[i + 1].id);
                else if (editorBackend.page < editorBackend.pageCount) editorBackend.setPage(editorBackend.page + 1);
                return;
            }
        }
    }

    Timer {
        id: liveCheckTimer
        interval: 150
        onTriggered: liveProblem.text = root.hasSelection ? editorBackend.checkText(transArea.text) : ""
    }

    Connections {
        target: editorBackend
        function onSelectedChanged() {
            var text = root.hasSelection ? root.selectedRow.translation : "";
            if (transArea.text !== text) transArea.text = text;
            liveCheckTimer.restart();
        }
    }

    // Compact icon + label button that sizes itself to its text.
    component ToolButton: Button {
        id: tool
        property string glyph: ""
        property string label: ""
        implicitHeight: 32
        implicitWidth: toolRow.implicitWidth + 28
        topInset: 0; bottomInset: 0; leftInset: 0; rightInset: 0; padding: 0
        opacity: enabled ? 1.0 : 0.45
        scale: down ? 0.97 : 1.0
        background: Rectangle {
            radius: Theme.radiusControl
            color: tool.hovered ? clrCardHover : Theme.surfaceControl
            border.color: tool.hovered ? Theme.borderFocus : Theme.borderControl
            border.width: 1
        }
        contentItem: Item {
            RowLayout {
                id: toolRow
                anchors.centerIn: parent
                spacing: 6
                Icon { glyph: tool.glyph; size: 14; color: tool.hovered ? clrTxt : clrTxt2 }
                Label { text: tool.label; font.pixelSize: 12; font.weight: Font.Medium; color: tool.hovered ? clrTxt : clrTxt2 }
            }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 20
        spacing: 12

        // Header & save action
        RowLayout {
            Layout.fillWidth: true
            spacing: 12

            Rectangle {
                width: 38; height: 38; radius: 10
                color: tint(clrAccent, 0.12)
                border.color: tint(clrAccent, 0.3); border.width: 1
                Icon { anchors.centerIn: parent; glyph: Icons.squarePen; size: 20; color: clrAccent }
            }

            ColumnLayout {
                spacing: 2
                Label {
                    text: root.tr("editor.title")
                    font.pixelSize: 22
                    font.bold: true
                    color: Theme.textPrimary
                }
                Label {
                    text: root.hasSession
                          ? root.tr("editor.subtitle")
                                .replace("{total}", editorBackend.totalCount)
                                .replace("{ready}", editorBackend.shippableCount)
                                .replace("{lang}", editorBackend.targetLanguage)
                          : root.tr("editor.subtitle_empty")
                    font.pixelSize: 13
                    color: Theme.textSecondary
                }
            }

            Item { Layout.fillWidth: true }

            ToolButton {
                Layout.alignment: Qt.AlignVCenter
                glyph: Icons.replace
                label: root.tr("editor.replace_btn")
                visible: root.hasSession
                implicitHeight: Theme.heightSecondary
                onClicked: { root.commit(); replacePopup.open(); }
            }

            Button {
                Layout.alignment: Qt.AlignVCenter
                implicitHeight: Theme.heightSecondary
                topInset: 0; bottomInset: 0; leftInset: 0; rightInset: 0; padding: 0
                enabled: root.hasSession && editorBackend.shippableCount > 0
                opacity: enabled ? 1.0 : 0.45
                scale: down ? 0.97 : (hovered ? 1.02 : 1.0)
                Behavior on scale { NumberAnimation { duration: 100 } }
                implicitWidth: saveRow.implicitWidth + 28
                background: Rectangle {
                    radius: Theme.radiusControl
                    color: parent.hovered ? Theme.statusSuccessSubtle : Theme.surfaceControl
                    border.color: parent.hovered ? Theme.statusSuccess : Theme.statusSuccessBorder
                    border.width: 1
                }
                contentItem: Item {
                    RowLayout {
                        id: saveRow
                        anchors.centerIn: parent
                        spacing: 6
                        Icon { glyph: Icons.save; size: 14; color: Theme.statusSuccess }
                        Label {
                            text: root.tr("editor.save_btn")
                            color: Theme.statusSuccess
                            font.pixelSize: 13
                            font.bold: true
                        }
                    }
                }
                onClicked: {
                    root.commit();
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
                        { key: "modified", label: root.tr("editor.filter_modified") },
                        { key: "warnings", label: root.tr("editor.filter_warnings") },
                        { key: "repaired", label: root.tr("editor.status_repaired") },
                        { key: "accepted", label: root.tr("editor.status_accepted") },
                        { key: "unchanged", label: root.tr("editor.status_unchanged") }
                    ]
                    delegate: Rectangle {
                        readonly property bool active: editorBackend && editorBackend.statusFilter === modelData.key
                        readonly property color chipColor: modelData.key === "" ? clrTxt
                            : (modelData.key === "modified" ? clrAccent
                               : (modelData.key === "warnings" ? clrError : root.statusColor(modelData.key)))
                        readonly property int chipCount: !editorBackend ? 0
                            : (modelData.key === "" ? editorBackend.totalCount : (editorBackend.counts[modelData.key] || 0))
                        height: Theme.heightBadge; radius: Theme.radiusBadge
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
                            onClicked: { root.commit(); editorBackend.setStatusFilter(modelData.key); }
                        }
                    }
                }
            }

            Rectangle {
                Layout.preferredWidth: 280
                height: Theme.heightInput
                radius: Theme.radiusControl
                color: clrInput
                border.color: searchInput.activeFocus ? clrAccent : clrCardBorder
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
                        onTextChanged: { root.commit(); editorBackend.setFilterQuery(text); }

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

        // Rows of the current page
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: 120
            radius: Theme.radiusCard
            color: Theme.isDark ? "#080C13" : Theme.surfaceControl
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
                anchors.margins: 8
                clip: true
                spacing: 4
                visible: root.hasSession
                model: editorBackend ? editorBackend.filteredRows : []
                boundsBehavior: Flickable.StopAtBounds
                ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                delegate: Rectangle {
                    readonly property bool current: root.hasSelection && root.selectedRow.id === modelData.id
                    width: rowList.width - 12
                    height: 54
                    radius: Theme.radiusControl
                    color: current ? root.tint(clrAccent, 0.10) : (rowMouse.containsMouse ? clrCardHover : clrCard)
                    border.color: current ? clrAccent : root.tint(root.statusColor(modelData.status), 0.35)
                    border.width: current ? 1.5 : 1

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 10; anchors.rightMargin: 10
                        spacing: 10

                        Rectangle {
                            Layout.alignment: Qt.AlignVCenter
                            implicitWidth: 124; implicitHeight: 20; radius: 4
                            color: root.tint(root.statusColor(modelData.status), 0.18)
                            border.color: root.statusColor(modelData.status); border.width: 1
                            Label {
                                anchors.centerIn: parent
                                width: parent.width - 8
                                horizontalAlignment: Text.AlignHCenter
                                elide: Text.ElideRight
                                text: root.tr("editor.status_" + modelData.status, modelData.status)
                                font.pixelSize: 10
                                font.bold: true
                                color: root.statusColor(modelData.status)
                            }
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            Layout.alignment: Qt.AlignVCenter
                            spacing: 2
                            Label {
                                Layout.fillWidth: true
                                text: root.oneLine(modelData.original)
                                textFormat: Text.PlainText
                                elide: Text.ElideRight
                                maximumLineCount: 1
                                font.pixelSize: 11
                                color: clrTxtDim
                            }
                            Label {
                                Layout.fillWidth: true
                                text: root.oneLine(modelData.translation)
                                textFormat: Text.PlainText
                                elide: Text.ElideRight
                                maximumLineCount: 1
                                font.pixelSize: 13
                                color: clrTxt
                                horizontalAlignment: editorBackend && editorBackend.isRtl ? Text.AlignRight : Text.AlignLeft
                            }
                        }

                        Rectangle {
                            visible: modelData.dirty
                            Layout.alignment: Qt.AlignVCenter
                            width: 8; height: 8; radius: 4
                            color: clrAccent
                        }
                        Icon {
                            visible: modelData.errors.length > 0
                            glyph: Icons.triangleAlert
                            size: 14
                            color: clrError
                            Layout.alignment: Qt.AlignVCenter
                        }
                    }

                    MouseArea {
                        id: rowMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.selectRow(modelData.id)
                    }
                }
            }
        }

        // Pager
        RowLayout {
            Layout.fillWidth: true
            visible: root.hasSession && editorBackend.matchCount > 0
            spacing: 8

            Label {
                text: root.tr("editor.matches").replace("{count}", editorBackend ? editorBackend.matchCount : 0)
                font.pixelSize: 11
                color: clrTxtDim
            }
            Item { Layout.fillWidth: true }

            component PageButton: Button {
                property string glyph: ""
                implicitWidth: 34; implicitHeight: 28
                topInset: 0; bottomInset: 0; leftInset: 0; rightInset: 0; padding: 0
                opacity: enabled ? 1.0 : 0.4
                background: Rectangle {
                    radius: Theme.radiusControl
                    color: parent.hovered ? clrCardHover : clrInput
                    border.color: clrCardBorder; border.width: 1
                }
                contentItem: Label {
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    text: parent.glyph
                    font.pixelSize: 15
                    color: clrTxt
                }
            }

            PageButton { glyph: "«"; enabled: editorBackend.page > 1; onClicked: root.goPage(1) }
            PageButton { glyph: "‹"; enabled: editorBackend.page > 1; onClicked: root.goPage(editorBackend.page - 1) }
            Label {
                text: root.tr("editor.page_label")
                        .replace("{page}", editorBackend.page)
                        .replace("{pages}", editorBackend.pageCount)
                font.pixelSize: 12
                color: clrTxt2
            }
            PageButton { glyph: "›"; enabled: editorBackend.page < editorBackend.pageCount; onClicked: root.goPage(editorBackend.page + 1) }
            PageButton { glyph: "»"; enabled: editorBackend.page < editorBackend.pageCount; onClicked: root.goPage(editorBackend.pageCount) }
        }

        // Detail of the selected row
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: Math.min(270, Math.max(210, root.height * 0.30))
            visible: root.hasSession
            radius: Theme.radiusCard
            color: clrCard
            border.color: clrCardBorder
            border.width: 1

            Label {
                anchors.centerIn: parent
                visible: !root.hasSelection
                text: root.tr("editor.select_hint")
                font.pixelSize: 13
                color: clrTxt2
            }

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 12
                spacing: 8
                visible: root.hasSelection

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    Rectangle {
                        implicitWidth: detailStatus.implicitWidth + 14; implicitHeight: 20; radius: 4
                        color: root.tint(root.statusColor(root.selectedRow.status || ""), 0.18)
                        border.color: root.statusColor(root.selectedRow.status || ""); border.width: 1
                        Label {
                            id: detailStatus
                            anchors.centerIn: parent
                            text: root.tr("editor.status_" + (root.selectedRow.status || ""), root.selectedRow.status || "")
                            font.pixelSize: 10
                            font.bold: true
                            color: root.statusColor(root.selectedRow.status || "")
                        }
                    }
                    Label {
                        text: root.tr("editor.row_label").replace("{n}", root.selectedRow.position || 0)
                        font.pixelSize: 11
                        color: clrTxtDim
                    }
                    Label {
                        visible: root.selectedRow.dirty === true
                        text: "● " + root.tr("editor.modified_marker")
                        font.pixelSize: 11
                        color: clrAccent
                    }
                    Item { Layout.fillWidth: true }
                    ToolButton {
                        glyph: Icons.undo2
                        label: root.tr("editor.revert_btn")
                        enabled: root.selectedRow.dirty === true
                        onClicked: editorBackend.revertSelected()
                    }
                    ToolButton {
                        glyph: Icons.circleCheck
                        label: root.tr("editor.apply_next_btn")
                        onClicked: root.commitAndNext()
                    }
                }

                // Source text (selectable)
                ScrollView {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 48
                    clip: true
                    Basic.TextArea {
                        padding: 8
                        readOnly: true
                        selectByMouse: true
                        wrapMode: TextEdit.Wrap
                        text: root.selectedRow.original || ""
                        font.pixelSize: 12
                        color: clrTxt2
                        background: Rectangle {
                            radius: Theme.radiusControl
                            color: Theme.surfaceSubtle
                            border.color: clrCardBorder; border.width: 1
                        }
                    }
                }

                // Tags and placeholders of the source that the translation must keep
                Flow {
                    Layout.fillWidth: true
                    spacing: 6
                    visible: root.hasSelection && (root.selectedRow.tokens || []).length > 0

                    Label {
                        text: root.tr("editor.tokens_label")
                        font.pixelSize: 11
                        color: clrTxtDim
                    }
                    Repeater {
                        model: root.selectedRow.tokens || []
                        delegate: Rectangle {
                            height: 20; radius: 4
                            width: tokenText.implicitWidth + 12
                            color: root.tint(clrAccent, 0.12)
                            border.color: root.tint(clrAccent, 0.4); border.width: 1
                            Label {
                                id: tokenText
                                anchors.centerIn: parent
                                text: modelData
                                textFormat: Text.PlainText
                                font.pixelSize: 11
                                font.family: "Consolas, 'Cascadia Code', monospace"
                                color: clrAccent
                            }
                        }
                    }
                }

                // Translation
                ScrollView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    // Basic style: Material's floating label and insets fight the custom background.
                    Basic.TextArea {
                        id: transArea
                        padding: 9
                        wrapMode: TextEdit.Wrap
                        selectByMouse: true
                        font.pixelSize: 13
                        color: clrTxt
                        selectionColor: root.tint(clrAccent, 0.35)
                        horizontalAlignment: editorBackend && editorBackend.isRtl ? Text.AlignRight : Text.AlignLeft
                        placeholderText: root.tr("editor.translation_placeholder")
                        placeholderTextColor: clrTxtDim
                        background: Rectangle {
                            radius: Theme.radiusControl
                            color: clrInput
                            border.color: transArea.activeFocus ? Theme.borderFocus : Theme.borderControl
                            border.width: 1
                        }
                        onTextChanged: liveCheckTimer.restart()
                        onActiveFocusChanged: { if (!activeFocus) root.commit(); }
                        Keys.onPressed: (event) => {
                            if ((event.modifiers & Qt.ControlModifier)
                                    && (event.key === Qt.Key_Return || event.key === Qt.Key_Enter)) {
                                root.commitAndNext();
                                event.accepted = true;
                            }
                        }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 6
                    visible: liveProblem.text.length > 0 || (root.selectedRow.errors || "").length > 0
                    Icon { glyph: Icons.triangleAlert; size: 14; color: clrError; Layout.alignment: Qt.AlignTop }
                    Label {
                        id: liveProblem
                        Layout.fillWidth: true
                        textFormat: Text.PlainText
                        wrapMode: Text.WordWrap
                        text: ""
                        font.pixelSize: 11
                        color: clrError
                    }
                }
            }
        }
    }

    Popup {
        id: replacePopup
        modal: true
        focus: true
        anchors.centerIn: Overlay.overlay
        width: Math.min(root.width - 48, 460)
        padding: 18
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

        background: Rectangle {
            radius: Theme.radiusCard
            color: Theme.surfaceCard
            border.color: Theme.borderCard
            border.width: 1
        }

        contentItem: ColumnLayout {
            spacing: 10

            Label {
                text: root.tr("editor.replace_title")
                font.pixelSize: 16
                font.bold: true
                color: clrTxt
            }
            Label {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                text: root.tr("editor.replace_scope").replace("{count}", editorBackend ? editorBackend.matchCount : 0)
                font.pixelSize: 11
                color: clrTxt2
            }
            Basic.TextField {
                id: findField
                Layout.fillWidth: true
                placeholderText: root.tr("editor.find_label")
                color: clrTxt
                placeholderTextColor: clrTxtDim
                font.pixelSize: 13
                background: Rectangle { radius: Theme.radiusControl; color: clrInput; border.color: findField.activeFocus ? Theme.borderFocus : Theme.borderControl; border.width: 1 }
            }
            Basic.TextField {
                id: replaceField
                Layout.fillWidth: true
                placeholderText: root.tr("editor.replace_with")
                color: clrTxt
                placeholderTextColor: clrTxtDim
                font.pixelSize: 13
                background: Rectangle { radius: Theme.radiusControl; color: clrInput; border.color: replaceField.activeFocus ? Theme.borderFocus : Theme.borderControl; border.width: 1 }
            }
            CheckBox {
                id: caseBox
                text: root.tr("editor.match_case")
                font.pixelSize: 12
            }
            Label {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                text: root.tr("editor.replace_note")
                textFormat: Text.PlainText
                font.pixelSize: 11
                color: clrTxtDim
            }
            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                Item { Layout.fillWidth: true }
                SecondaryButton {
                    text: root.tr("editor.replace_cancel")
                    onClicked: replacePopup.close()
                }
                PrimaryButton {
                    text: root.tr("editor.replace_apply")
                    iconGlyph: Icons.replace
                    enabled: findField.text.length > 0
                    implicitHeight: Theme.heightSecondary
                    onClicked: {
                        editorBackend.replaceAll(findField.text, replaceField.text, caseBox.checked);
                        replacePopup.close();
                    }
                }
            }
        }
    }
}
