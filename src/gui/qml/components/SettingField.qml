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
        color: "#9CA3AF"
        font.pixelSize: 12
        font.bold: true
    }

    // Basic style: Material's floating placeholder overlaps the label when a value is set.
    Basic.TextField {
        id: input
        Layout.fillWidth: true
        Layout.preferredHeight: 40
        leftPadding: 12
        rightPadding: 12
        verticalAlignment: TextInput.AlignVCenter
        placeholderTextColor: "#6B7280"
        selectionColor: Qt.rgba(0, 0.95, 1, 0.35)
        text: field.storedValue
        echoMode: field.password ? TextInput.Password : TextInput.Normal
        placeholderText: field.placeholder
        color: "#F3F4F6"
        selectByMouse: true
        background: Rectangle {
            radius: 8
            color: "#0E121D"
            border.color: input.activeFocus ? "#00F2FE" : "#242C44"
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
        color: "#6B7280"
        font.pixelSize: 11
    }
}
