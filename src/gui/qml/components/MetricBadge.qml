import QtQuick
import QtQuick.Controls.Material

Rectangle {
    id: root
    property string title: ""
    property string value: ""
    property color accentColor: Material.accentColor

    implicitWidth: 160
    implicitHeight: 64
    radius: 8
    color: "#252528"
    border.color: "#353538"
    border.width: 1

    Column {
        anchors.centerIn: parent
        spacing: 4

        Text {
            text: root.title
            font.pixelSize: 11
            color: "#888888"
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
