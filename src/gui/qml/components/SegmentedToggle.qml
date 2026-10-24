import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: root

    property var model: []
    property var currentValue: null
    signal selectionChanged(var value)

    implicitHeight: Theme.heightSecondary
    implicitWidth: rowLayout.implicitWidth

    RowLayout {
        id: rowLayout
        anchors.fill: parent
        spacing: 6

        Repeater {
            model: root.model

            Button {
                id: segBtn
                readonly property bool isActive: root.currentValue === segBtn.itemValue
                readonly property string itemText: (modelData && modelData.label !== undefined) ? modelData.label : modelData
                readonly property var itemValue: (modelData && modelData.value !== undefined) ? modelData.value : modelData
                readonly property string itemIcon: (modelData && modelData.icon) ? modelData.icon : ""

                Layout.preferredHeight: Theme.heightSecondary
                Layout.fillWidth: true
                topInset: 0
                bottomInset: 0
                leftInset: 0
                rightInset: 0
                padding: 0
                scale: down ? 0.98 : 1.0

                onClicked: {
                    root.currentValue = segBtn.itemValue;
                    root.selectionChanged(segBtn.itemValue);
                }

                background: Rectangle {
                    radius: Theme.radiusControl
                    color: {
                        if (segBtn.isActive) return Theme.accentSubtle;
                        return segBtn.hovered ? Theme.surfaceHover : Theme.surfaceControl;
                    }
                    border.color: {
                        if (segBtn.isActive) return Theme.accentBorder;
                        return segBtn.hovered ? Theme.borderFocus : Theme.borderControl;
                    }
                    border.width: 1

                    Behavior on color { ColorAnimation { duration: 120 } }
                    Behavior on border.color { ColorAnimation { duration: 120 } }
                }

                contentItem: RowLayout {
                    spacing: 6
                    anchors.centerIn: parent

                    Icon {
                        visible: segBtn.itemIcon !== ""
                        glyph: segBtn.itemIcon
                        size: 14
                        color: segBtn.isActive 
                               ? (Theme.isDark ? Theme.accentHover : Theme.accentSolid)
                               : (segBtn.hovered ? Theme.textPrimary : Theme.textSecondary)
                    }

                    Label {
                        text: segBtn.itemText
                        textFormat: Text.PlainText
                        font.pixelSize: 13
                        font.bold: segBtn.isActive
                        font.weight: segBtn.isActive ? Font.DemiBold : Font.Normal
                        color: segBtn.isActive
                               ? (Theme.isDark ? Theme.accentHover : Theme.accentSolid)
                               : (segBtn.hovered ? Theme.textPrimary : Theme.textSecondary)
                        elide: Text.ElideRight
                    }
                }
            }
        }
    }
}
