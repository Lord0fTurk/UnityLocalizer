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

    // Writes the typed value, then shows what the backend really kept: it trims text, clamps
    // numbers and refuses garbage, and a refused edit must not stay on screen as if it were saved.
    function commit() {
        if (!appBackend || input.text === field.storedValue) return;
        var before = field.storedValue;
        appBackend.setSetting(field.key, input.text);
        var kept = field.storedValue;
        if (input.text !== kept) input.text = kept;
        feedback.show(kept !== before);
    }

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
        rightPadding: 34
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
        onEditingFinished: field.commit()
        onActiveFocusChanged: { if (!activeFocus) field.commit(); }
        Component.onDestruction: {
            if (appBackend && text !== field.storedValue) appBackend.setSetting(field.key, text);
        }

        // Decorative status mark: a check after a save, an alert when the edit was not kept.
        Icon {
            id: feedback
            property bool accepted: true
            anchors.right: parent.right
            anchors.rightMargin: 10
            anchors.verticalCenter: parent.verticalCenter
            glyph: accepted ? Icons.circleCheck : Icons.triangleAlert
            color: accepted ? Theme.statusSuccess : Theme.statusDanger
            size: 16
            opacity: 0
            Accessible.ignored: true

            function show(ok) {
                accepted = ok;
                opacity = 1;
                fade.restart();
            }

            Behavior on opacity { NumberAnimation { duration: 250 } }
            Timer {
                id: fade
                interval: 1600
                onTriggered: feedback.opacity = 0
            }
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
