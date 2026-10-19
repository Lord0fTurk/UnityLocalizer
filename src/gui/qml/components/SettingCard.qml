import QtQuick
import QtQuick.Controls.Material
import QtQuick.Layouts

// Settings section card: icon + title (+ optional badge), description, then children.
Rectangle {
    id: card

    property string icon: ""
    property string title: ""
    property string description: ""
    property string badge: ""
    default property alias content: body.data

    width: parent ? parent.width : 400
    implicitHeight: column.implicitHeight + 36
    radius: 14
    color: "#151A29"
    border.color: "#242C44"
    border.width: 1

    ColumnLayout {
        id: column
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.margins: 18
        spacing: 12

        RowLayout {
            Layout.fillWidth: true
            Label {
                text: (card.icon ? card.icon + " " : "") + card.title
                font.pixelSize: 16
                font.bold: true
                color: "#F3F4F6"
            }
            Item { Layout.fillWidth: true }
            Rectangle {
                visible: card.badge.length > 0
                implicitWidth: badgeLabel.implicitWidth + 16
                implicitHeight: 22
                radius: 11
                color: Qt.rgba(0, 0.95, 1, 0.12)
                border.color: Qt.rgba(0, 0.95, 1, 0.4)
                Label {
                    id: badgeLabel
                    anchors.centerIn: parent
                    text: card.badge
                    font.pixelSize: 10
                    font.bold: true
                    color: "#00F2FE"
                }
            }
        }

        Label {
            Layout.fillWidth: true
            visible: card.description.length > 0
            text: card.description
            wrapMode: Text.WordWrap
            font.pixelSize: 12
            color: "#9CA3AF"
        }

        ColumnLayout {
            id: body
            Layout.fillWidth: true
            spacing: 12
        }
    }
}
