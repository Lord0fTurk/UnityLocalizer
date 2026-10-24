import QtQuick
import QtQuick.Controls.Material
import QtQuick.Layouts

// Boolean setting (checkbox + optional explanation), saved immediately on toggle.
ColumnLayout {
    id: toggle

    property string key: ""
    property string label: ""
    property string description: ""

    Layout.fillWidth: true
    spacing: 2

    CheckBox {
        Layout.fillWidth: true
        text: toggle.label
        checked: Boolean(appBackend && appBackend.settings[toggle.key])
        Material.accent: Theme.accentSolid
        onToggled: {
            if (appBackend) appBackend.setSetting(toggle.key, checked);
        }
    }

    Label {
        Layout.fillWidth: true
        Layout.leftMargin: 12
        visible: toggle.description.length > 0
        text: toggle.description
        wrapMode: Text.WordWrap
        font.pixelSize: 11
        color: Theme.textMuted
    }
}
