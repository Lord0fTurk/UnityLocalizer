import QtQuick
// Explicit Material import: the platform-default (native Windows) style cannot be customized.
import QtQuick.Controls.Material
import QtQuick.Layouts

// Dashboard-styled picker: a metric-badge tile that opens a searchable dark popup.
// Model rows are objects; `valueRole` names the key compared with `currentValue`,
// `name` is displayed and `english`/`native`/`code` (when present) are searchable.
Rectangle {
    id: root

    property string caption: ""
    property string icon: ""
    property string iconGlyph: ""
    property var model: []
    property string valueRole: "code"
    property string currentValue: ""
    property bool searchable: false
    property string searchPlaceholder: ""
    property string emptyText: ""
    property color accent: Theme.accentSolid
    property bool warning: false

    signal activated(string value)

    readonly property var currentRow: {
        for (var i = 0; i < model.length; i++) {
            if (model[i][valueRole] === currentValue) return model[i];
        }
        return null;
    }

    function open() { popup.open(); }

    implicitHeight: 70
    radius: Theme.radiusCard
    color: tileMouse.containsMouse && enabled ? Theme.surfaceHover : Theme.surfaceControl
    border.width: 1
    border.color: popup.opened ? (Theme.isNeon ? Theme.accentHover : root.accent)
                 : warning ? Theme.statusWarning
                 : (tileMouse.containsMouse && enabled ? Theme.borderFocus : Theme.borderControl)
    opacity: enabled ? 1.0 : 0.55
    scale: tileMouse.pressed ? 0.985 : 1.0
    Behavior on color { ColorAnimation { duration: 120 } }
    Behavior on border.color { ColorAnimation { duration: 120 } }
    Behavior on scale { NumberAnimation { duration: 90 } }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 14
        anchors.rightMargin: 12
        spacing: 10

        Icon {
            visible: root.iconGlyph.length > 0
            glyph: root.iconGlyph
            size: 18
            color: root.accent
        }

        Text {
            visible: root.iconGlyph.length === 0 && root.icon.length > 0
            text: root.icon
            font.pixelSize: 18
        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 3

            Text {
                text: root.caption
                font.pixelSize: 11
                color: Theme.textSecondary
            }
            Text {
                id: valueText
                Layout.fillWidth: true
                horizontalAlignment: Text.AlignLeft
                text: root.currentRow ? root.currentRow.name : root.currentValue
                font.pixelSize: 14
                font.bold: true
                color: root.warning ? Theme.statusWarning : Theme.textPrimary
                elide: Text.ElideRight
            }
        }

        Text {
            text: "▾"
            font.pixelSize: 14
            color: popup.opened ? root.accent : Theme.textMuted
            rotation: popup.opened ? 180 : 0
            Behavior on rotation { NumberAnimation { duration: 140 } }
        }
    }

    MouseArea {
        id: tileMouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: root.enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
        onClicked: if (root.enabled) popup.open()

        ToolTip.visible: containsMouse && valueText.truncated && !popup.opened
        ToolTip.delay: 400
        ToolTip.text: valueText.text
    }

    function matches(row, needle) {
        if (!needle) return true;
        var fields = [row.name, row.english, row.native, row.code, row.id];
        for (var i = 0; i < fields.length; i++) {
            if (fields[i] && String(fields[i]).toLowerCase().indexOf(needle) >= 0) return true;
        }
        return false;
    }

    Popup {
        id: popup
        y: root.height + 6
        width: Math.max(root.width, 300)
        height: Math.min(420, listView.contentHeight + (root.searchable ? 58 : 12) + 2)
        padding: 6
        focus: true
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

        property var filtered: {
            var needle = searchField.text.trim().toLowerCase();
            var out = [];
            for (var i = 0; i < root.model.length; i++) {
                if (root.matches(root.model[i], needle)) out.push(root.model[i]);
            }
            return out;
        }

        onOpened: {
            searchField.text = "";
            if (root.searchable) searchField.forceActiveFocus();
            for (var i = 0; i < filtered.length; i++) {
                if (filtered[i][root.valueRole] === root.currentValue) {
                    listView.positionViewAtIndex(i, ListView.Center);
                    break;
                }
            }
        }

        function choose(row) {
            if (!row) return;
            root.activated(row[root.valueRole]);
            popup.close();
        }

        background: Rectangle {
            radius: Theme.radiusCard
            color: Theme.surfaceCard
            border.color: Theme.borderCard
            border.width: 1
        }

        contentItem: ColumnLayout {
            spacing: 6

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: Theme.heightInput
                visible: root.searchable
                radius: Theme.radiusControl
                color: Theme.surfaceControl
                border.color: searchField.activeFocus ? Theme.borderFocus : Theme.borderControl
                border.width: 1

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 10
                    anchors.rightMargin: 10
                    spacing: 8

                    Icon { glyph: Icons.search; size: 14; color: Theme.textMuted }

                    TextInput {
                        id: searchField
                        Layout.fillWidth: true
                        font.pixelSize: 13
                        color: Theme.textPrimary
                        clip: true
                        selectByMouse: true
                        Keys.onReturnPressed: popup.choose(popup.filtered[0])
                        Keys.onEnterPressed: popup.choose(popup.filtered[0])
                        Keys.onDownPressed: listView.forceActiveFocus()

                        Text {
                            anchors.fill: parent
                            verticalAlignment: Text.AlignVCenter
                            text: root.searchPlaceholder
                            color: Theme.textMuted
                            font.pixelSize: 13
                            visible: !searchField.text
                        }
                    }
                }
            }

            ListView {
                id: listView
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                model: popup.filtered
                boundsBehavior: Flickable.StopAtBounds
                keyNavigationEnabled: true
                ScrollBar.vertical: ScrollBar {
                    id: listScroll
                    policy: ScrollBar.AsNeeded
                    width: 6
                    background: Item {}
                    contentItem: Rectangle {
                        implicitWidth: 4
                        radius: 2
                        color: listScroll.pressed || listScroll.hovered ? root.accent : Theme.borderControl
                        opacity: listScroll.active ? 1.0 : 0.6
                    }
                }
                Keys.onReturnPressed: popup.choose(popup.filtered[currentIndex])

                delegate: Rectangle {
                    readonly property bool selected: modelData[root.valueRole] === root.currentValue
                    width: listView.width - 12
                    height: 36
                    radius: Theme.radiusControl
                    color: selected ? Theme.accentSubtle
                         : (rowMouse.containsMouse || ListView.isCurrentItem ? Theme.surfaceHover : "transparent")

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 10
                        anchors.rightMargin: 10
                        spacing: 8

                        Text {
                            Layout.fillWidth: true
                            text: modelData.name
                            // RTL names (Urdu, Uyghur...) must not flip the row alignment.
                            horizontalAlignment: Text.AlignLeft
                            font.pixelSize: 13
                            font.bold: selected
                            color: selected ? (Theme.isDark ? Theme.accentHover : Theme.accentSolid) : Theme.textPrimary
                            elide: Text.ElideRight
                        }
                        Text {
                            visible: modelData.code !== undefined
                            text: modelData.code || ""
                            font.pixelSize: 11
                            color: Theme.textMuted
                        }
                    }

                    MouseArea {
                        id: rowMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: popup.choose(modelData)
                    }
                }

                Text {
                    anchors.centerIn: parent
                    visible: popup.filtered.length === 0
                    text: root.emptyText
                    font.pixelSize: 12
                    color: Theme.textMuted
                }
            }
        }
    }
}
