// IconLabel.qml — Icon + Text component for buttons, tabs and headers.
// Usage: IconLabel { glyph: Icons.save; text: "Kaydet"; color: clrTxt }
import QtQuick
import QtQuick.Controls

Item {
    id: il
    property string glyph: ""
    property string text: ""
    property color color: Theme.textPrimary
    property color iconColor: color
    property int iconSize: Math.round(label.font.pixelSize * 1.2)
    property int spacing: 6
    property int leftPadding: 0
    property int alignment: Qt.AlignHCenter
    property alias font: label.font
    property alias elide: label.elide

    readonly property bool _hasIcon: glyph.length > 0
    readonly property real _gap: _hasIcon && text.length > 0 ? spacing : 0

    implicitWidth: leftPadding + (_hasIcon ? iconSize : 0) + _gap + label.implicitWidth
    implicitHeight: Math.max(_hasIcon ? iconSize : 0, label.implicitHeight)

    Row {
        id: row
        spacing: il._gap
        anchors.verticalCenter: parent.verticalCenter
        x: il.alignment === Qt.AlignHCenter ? (il.width - width) / 2
         : il.alignment === Qt.AlignRight ? Math.max(0, il.width - width) : il.leftPadding

        Icon {
            visible: il._hasIcon
            glyph: il.glyph
            size: il.iconSize
            color: il.iconColor
            anchors.verticalCenter: parent.verticalCenter
        }
        Label {
            id: label
            text: il.text
            color: il.color
            width: label.elide === Text.ElideNone || il.width <= 0 ? implicitWidth
                 : Math.min(implicitWidth, il.width - il.leftPadding - (il._hasIcon ? il.iconSize : 0) - il._gap)
            anchors.verticalCenter: parent.verticalCenter
        }
    }
}
