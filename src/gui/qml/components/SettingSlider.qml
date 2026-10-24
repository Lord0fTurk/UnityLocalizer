import QtQuick
import QtQuick.Controls.Material
import QtQuick.Layouts

// Numeric setting with live value label; saved when the handle is released.
ColumnLayout {
    id: slider

    property string key: ""
    property string label: ""
    property string hint: ""
    property string suffix: ""
    property real from: 0
    property real to: 100
    property real stepSize: 1
    property int decimals: 0

    readonly property real storedValue: appBackend && appBackend.settings[key] !== undefined
                                        ? Number(appBackend.settings[key]) : from

    Layout.fillWidth: true
    spacing: 2

    RowLayout {
        Layout.fillWidth: true
        Label {
            text: slider.label
            color: Theme.textSecondary
            font.pixelSize: 12
            font.bold: true
        }
        Item { Layout.fillWidth: true }
        Label {
            text: control.value.toFixed(slider.decimals) + slider.suffix
            color: Theme.isDark ? Theme.accentHover : Theme.accentSolid
            font.pixelSize: 12
            font.bold: true
        }
    }

    Slider {
        id: control
        Layout.fillWidth: true
        from: slider.from
        to: slider.to
        stepSize: slider.stepSize
        value: slider.storedValue
        Material.accent: Theme.accentSolid
        onPressedChanged: {
            if (!pressed && appBackend && Math.abs(value - slider.storedValue) > 1e-9) {
                appBackend.setSetting(slider.key, value);
            }
        }
    }

    Label {
        Layout.fillWidth: true
        visible: slider.hint.length > 0
        text: slider.hint
        wrapMode: Text.WordWrap
        color: Theme.textMuted
        font.pixelSize: 11
    }
}
