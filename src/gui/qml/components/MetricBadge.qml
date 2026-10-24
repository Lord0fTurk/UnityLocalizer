import QtQuick
import QtQuick.Controls.Material

Rectangle {
    id: root
    property string title: ""
    property string value: ""
    property color accentColor: Theme.isDark ? Theme.accentHover : Theme.accentSolid

    implicitWidth: 160
    implicitHeight: 64
    radius: Theme.radiusControl
    color: Theme.surfaceControl
    border.color: Theme.borderControl
    border.width: 1

    Column {
        anchors.centerIn: parent
        spacing: 4

        Text {
            text: root.title
            font.pixelSize: 11
            color: Theme.textSecondary
            anchors.horizontalCenter: parent.horizontalCenter
        }

        Text {
            text: root.value
            font.pixelSize: 15
            font.bold: true
            color: root.accentColor
            anchors.horizontalCenter: parent.horizontalCenter
        }
    }
}
