import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Button {
    id: root

    property string iconGlyph: ""
    property int iconSize: 16
    property bool destructive: false

    implicitHeight: Theme.heightSecondary
    implicitWidth: Math.max(100, btnContent.implicitWidth + 24)

    topInset: 0
    bottomInset: 0
    leftInset: 0
    rightInset: 0
    padding: 0

    scale: down ? 0.98 : (hovered ? 1.01 : 1.0)
    Behavior on scale { NumberAnimation { duration: 120; easing.type: Easing.OutCubic } }

    background: Rectangle {
        radius: Theme.radiusControl

        color: {
            if (!root.enabled) return Theme.isDark ? "#121722" : "#F1F5F9";
            if (root.destructive) {
                return root.down ? Qt.rgba(244/255, 63/255, 94/255, 0.22)
                     : (root.hovered ? Qt.rgba(244/255, 63/255, 94/255, 0.12) : "transparent");
            }
            return root.down ? Theme.surfaceHover : (root.hovered ? Theme.surfaceHover : Theme.surfaceControl);
        }

        border.color: {
            if (!root.enabled) return "transparent";
            if (root.destructive) {
                return root.hovered ? Theme.statusDanger : Qt.rgba(244/255, 63/255, 94/255, 0.35);
            }
            return root.hovered ? (Theme.isNeon ? Theme.accentHover : Theme.borderFocus) : Theme.borderControl;
        }
        border.width: 1

        Behavior on color { ColorAnimation { duration: 120 } }
        Behavior on border.color { ColorAnimation { duration: 120 } }
    }

    contentItem: RowLayout {
        id: btnContent
        spacing: 8
        anchors.centerIn: parent

        Icon {
            visible: root.iconGlyph !== ""
            glyph: root.iconGlyph
            size: root.iconSize
            color: {
                if (!root.enabled) return Theme.textMuted;
                if (root.destructive) return Theme.statusDanger;
                return root.hovered ? Theme.textPrimary : Theme.textSecondary;
            }
        }

        Label {
            text: root.text
            textFormat: Text.PlainText
            font.pixelSize: 13
            font.weight: Font.Medium
            color: {
                if (!root.enabled) return Theme.textMuted;
                if (root.destructive) return Theme.statusDanger;
                return root.hovered ? Theme.textPrimary : Theme.textSecondary;
            }
            elide: Text.ElideRight
        }
    }
}
