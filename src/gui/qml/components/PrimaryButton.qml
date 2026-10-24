import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Button {
    id: root

    property string iconGlyph: ""
    property int iconSize: 18
    property bool busy: false

    implicitHeight: Theme.heightPrimaryCTA
    implicitWidth: Math.max(140, btnContent.implicitWidth + 32)

    topInset: 0
    bottomInset: 0
    leftInset: 0
    rightInset: 0
    padding: 0

    scale: down ? 0.98 : (hovered ? 1.01 : 1.0)
    Behavior on scale { NumberAnimation { duration: 120; easing.type: Easing.OutCubic } }

    background: Rectangle {
        id: bgRect
        radius: Theme.radiusControl

        color: {
            if (!root.enabled) return Theme.isDark ? "#232A3B" : "#CBD5E1";
            if (Theme.isNeon) {
                return root.down ? Theme.accentAlpha(0.45) : (root.hovered ? Theme.accentAlpha(0.35) : Theme.accentAlpha(0.25));
            }
            return root.down ? Theme.accentSolid : (root.hovered ? Theme.accentHover : Theme.accentSolid);
        }

        border.color: {
            if (!root.enabled) return "transparent";
            if (Theme.isNeon) return root.hovered ? Theme.accentHover : Theme.accentAlpha(0.8);
            return "transparent";
        }
        border.width: Theme.isNeon ? 1.5 : 0

        Behavior on color { ColorAnimation { duration: 120 } }
        Behavior on border.color { ColorAnimation { duration: 120 } }

        // Cyber Neon dış parlama simülasyonu
        Rectangle {
            anchors.fill: parent
            anchors.margins: -2
            radius: bgRect.radius + 2
            color: "transparent"
            border.color: Theme.accentAlpha(0.3)
            border.width: 1
            visible: Theme.isNeon && root.hovered && root.enabled
            opacity: 0.8
        }
    }

    contentItem: RowLayout {
        id: btnContent
        spacing: 10
        anchors.centerIn: parent

        Icon {
            id: btnIcon
            visible: root.iconGlyph !== "" && !root.busy
            glyph: root.iconGlyph
            size: root.iconSize
            color: {
                if (!root.enabled) return Theme.textMuted;
                if (Theme.isNeon) return Theme.textPrimary;
                return Theme.accentContrastText;
            }
        }

        BusyIndicator {
            visible: root.busy
            running: root.busy
            Layout.preferredWidth: root.iconSize
            Layout.preferredHeight: root.iconSize
        }

        Label {
            text: root.text
            textFormat: Text.PlainText
            font.pixelSize: 14
            font.bold: true
            font.letterSpacing: 0.5
            color: {
                if (!root.enabled) return Theme.textMuted;
                if (Theme.isNeon) return Theme.textPrimary;
                return Theme.accentContrastText;
            }
            elide: Text.ElideRight
        }
    }
}
