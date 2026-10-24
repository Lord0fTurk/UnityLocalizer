import QtQuick
import QtQuick.Controls.Material
import QtQuick.Controls.Basic as Basic
import QtQuick.Layouts

// Multi-line setting (lists, prompts); saved when the field loses focus.
ColumnLayout {
    id: area

    property string key: ""
    property string label: ""
    property string placeholder: ""
    property string hint: ""
    property int minLines: 4

    readonly property string storedValue: appBackend && appBackend.settings[key] !== undefined
                                          ? String(appBackend.settings[key]) : ""

    Layout.fillWidth: true
    spacing: 4

    Label {
        visible: area.label.length > 0
        text: area.label
        color: Theme.textSecondary
        font.pixelSize: 12
        font.bold: true
    }

    // Basic style: Material's floating label fights the custom background.
    Basic.TextArea {
        id: input
        Layout.fillWidth: true
        Layout.preferredHeight: Math.max(area.minLines * 20 + 18, contentHeight + topPadding + bottomPadding)
        padding: 9
        text: area.storedValue
        wrapMode: TextEdit.Wrap
        selectByMouse: true
        font.pixelSize: 13
        color: Theme.textPrimary
        placeholderText: area.placeholder
        placeholderTextColor: Theme.textMuted
        background: Rectangle {
            radius: Theme.radiusControl
            color: Theme.surfaceControl
            border.color: input.activeFocus ? Theme.borderFocus : Theme.borderControl
            border.width: 1
        }
        onActiveFocusChanged: {
            if (!activeFocus && appBackend && text !== area.storedValue) appBackend.setSetting(area.key, text);
        }
        Component.onDestruction: {
            if (appBackend && text !== area.storedValue) appBackend.setSetting(area.key, text);
        }
    }

    Label {
        Layout.fillWidth: true
        visible: area.hint.length > 0
        text: area.hint
        wrapMode: Text.WordWrap
        color: Theme.textMuted
        font.pixelSize: 11
    }
}
