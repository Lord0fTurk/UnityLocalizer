import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root

    property string title: ""
    property string subtitle: ""
    property string iconGlyph: ""
    default property alias content: contentContainer.data
    property alias headerActions: headerActionsContainer.data

    radius: Theme.radiusCard
    color: Theme.surfaceCard
    border.color: Theme.borderCard
    border.width: 1

    implicitHeight: mainLayout.implicitHeight + 36
    implicitWidth: 400

    Behavior on color { ColorAnimation { duration: 140 } }
    Behavior on border.color { ColorAnimation { duration: 140 } }

    ColumnLayout {
        id: mainLayout
        anchors.fill: parent
        anchors.margins: 18
        spacing: 14

        // Card Header (Opsiyonel: Başlık veya headerActions varsa görünür)
        RowLayout {
            Layout.fillWidth: true
            visible: root.title !== "" || root.subtitle !== "" || headerActionsContainer.children.length > 0
            spacing: 10

            Icon {
                visible: root.iconGlyph !== ""
                glyph: root.iconGlyph
                size: 18
                color: Theme.accentSolid
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2

                Label {
                    visible: root.title !== ""
                    text: root.title
                    font.pixelSize: 15
                    font.bold: true
                    color: Theme.textPrimary
                }

                Label {
                    visible: root.subtitle !== ""
                    text: root.subtitle
                    font.pixelSize: 12
                    color: Theme.textSecondary
                }
            }

            Item {
                id: headerActionsContainer
                Layout.alignment: Qt.AlignRight | Qt.AlignVCenter
                implicitWidth: childrenRect.width
                implicitHeight: childrenRect.height
            }
        }

        // Separator (Başlık varsa ve içerik varsa ince ayırıcı)
        Rectangle {
            Layout.fillWidth: true
            height: 1
            color: Theme.borderCard
            visible: (root.title !== "" || root.subtitle !== "") && contentContainer.children.length > 0
            opacity: 0.6
        }

        // Content slot
        Item {
            id: contentContainer
            Layout.fillWidth: true
            Layout.fillHeight: true
            implicitHeight: childrenRect.height
        }
    }
}
