import QtQuick
import QtQuick.Controls.Material
import QtQuick.Layouts

// Settings section card: icon + title (+ optional badge), description, then children.
Rectangle {
    id: card

    property string icon: ""
    property string iconGlyph: ""
    property string title: ""
    property string description: ""
    property string badge: ""
    default property alias content: body.data

    width: parent ? parent.width : 400
    implicitHeight: column.implicitHeight + 36
    radius: Theme.radiusCard
    color: Theme.surfaceCard
    border.color: Theme.borderCard
    border.width: 1

    Behavior on color { ColorAnimation { duration: 140 } }
    Behavior on border.color { ColorAnimation { duration: 140 } }

    ColumnLayout {
        id: column
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.margins: 18
        spacing: 12

        RowLayout {
            Layout.fillWidth: true
            spacing: 10

            Icon {
                visible: card.iconGlyph !== ""
                glyph: card.iconGlyph
                size: 18
                color: Theme.accentSolid
            }

            Text {
                visible: card.icon !== "" && card.iconGlyph === ""
                text: card.icon
                font.pixelSize: 18
            }

            Label {
                text: card.title
                font.pixelSize: 15
                font.bold: true
                color: Theme.textPrimary
            }
            Item { Layout.fillWidth: true }
            Rectangle {
                visible: card.badge.length > 0
                implicitWidth: badgeLabel.implicitWidth + 16
                implicitHeight: Theme.heightBadge
                radius: Theme.radiusBadge
                color: Theme.accentSubtle
                border.color: Theme.accentBorder
                border.width: 1
                Label {
                    id: badgeLabel
                    anchors.centerIn: parent
                    text: card.badge
                    textFormat: Text.PlainText
                    font.pixelSize: 10
                    font.bold: true
                    color: Theme.isDark ? Theme.accentHover : Theme.accentSolid
                }
            }
        }

        Label {
            Layout.fillWidth: true
            visible: card.description.length > 0
            text: card.description
            wrapMode: Text.WordWrap
            font.pixelSize: 12
            color: Theme.textSecondary
        }

        ColumnLayout {
            id: body
            Layout.fillWidth: true
            spacing: 12
        }
    }
}
