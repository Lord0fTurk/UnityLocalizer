// Icon.qml — Lucide icon within a square container for aligned layouts.
// Usage: Icon { glyph: Icons.search; size: 14; color: clrTxt2 }
import QtQuick

Item {
    id: icon
    property string glyph: ""
    property int size: 16
    property color color: Theme.textPrimary

    implicitWidth: size
    implicitHeight: size

    Text {
        anchors.centerIn: parent
        text: icon.glyph
        color: icon.color
        font.family: Icons.family
        font.pixelSize: icon.size
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }
}
