import QtQuick
import QtQuick.Controls.Material
import QtQuick.Controls.Basic as Basic
import QtQuick.Layouts

// Single-line text setting bound to appBackend.settings[key]; saved when editing finishes.
ColumnLayout {
    id: field

    property string key: ""
    property string label: ""
    property string placeholder: ""
    property string hint: ""
    property bool password: false

    readonly property string storedValue: appBackend && appBackend.settings[key] !== undefined
                                          ? String(appBackend.settings[key]) : ""

    Layout.fillWidth: true
    spacing: 4

    Label {
        visible: field.label.length > 0
        text: field.label
        color: Theme.textSecondary
        font.pixelSize: 12
        font.bold: true
    }

    // Basic style: Material's floating placeholder overlaps the label when a value is set.
    Basic.TextField {
        id: input
        Layout.fillWidth: true
        Layout.preferredHeight: Theme.heightInput
        leftPadding: 12
        rightPadding: 12
        verticalAlignment: TextInput.AlignVCenter
        placeholderTextColor: Theme.textMuted
        selectionColor: Theme.accentAlpha(0.35)
        text: field.storedValue
        echoMode: field.password ? TextInput.Password : TextInput.Normal
        placeholderText: field.placeholder
        color: Theme.textPrimary
        selectByMouse: true
        background: Rectangle {
            radius: Theme.radiusControl
            color: Theme.surfaceControl
            border.color: input.activeFocus ? Theme.borderFocus : Theme.borderControl
            border.width: 1
        }
        onEditingFinished: {
            if (appBackend && text !== field.storedValue) appBackend.setSetting(field.key, text);
        }
        onActiveFocusChanged: {
            if (!activeFocus && appBackend && text !== field.storedValue) appBackend.setSetting(field.key, text);
        }
        Component.onDestruction: {
            if (appBackend && text !== field.storedValue) appBackend.setSetting(field.key, text);
        }
    }

    Label {
        Layout.fillWidth: true
        visible: field.hint.length > 0
        text: field.hint
        wrapMode: Text.WordWrap
        color: Theme.textMuted
        font.pixelSize: 11
    }
}
