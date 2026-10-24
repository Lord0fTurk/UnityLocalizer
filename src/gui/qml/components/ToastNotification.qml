import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: root
    width: Math.min(380, parent.width - 32)
    height: toastCard.height
    anchors.right: parent.right
    anchors.bottom: parent.bottom
    anchors.margins: 20
    visible: opacity > 0
    opacity: 0

    property string message: ""
    property string toastType: "info" // "success", "error", "warning", "info"

    function show(msg, type) {
        message = msg;
        toastType = type || "info";
        root.opacity = 1.0;
        toastCard.y = 0;
        dismissTimer.restart();
    }

    Timer {
        id: dismissTimer
        interval: 4000
        onTriggered: {
            root.opacity = 0.0;
            toastCard.y = 20;
        }
    }

    Rectangle {
        id: toastCard
        width: parent.width
        implicitHeight: contentRow.implicitHeight + 24
        radius: Theme.radiusCard
        color: Theme.surfaceCard
        border.width: 1
        border.color: {
            if (toastType === "success") return Theme.statusSuccess;
            if (toastType === "error") return Theme.statusDanger;
            if (toastType === "warning") return Theme.statusWarning;
            return Theme.accentSolid;
        }

        y: 20
        Behavior on y { NumberAnimation { duration: 250; easing.type: Easing.OutCubic } }
        Behavior on opacity { NumberAnimation { duration: 200 } }

        RowLayout {
            id: contentRow
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: 14
            spacing: 12

            Text {
                text: {
                    if (toastType === "success") return "✅";
                    if (toastType === "error") return "❌";
                    if (toastType === "warning") return "⚠️";
                    return "ℹ️";
                }
                font.pixelSize: 18
            }

            Text {
                Layout.fillWidth: true
                text: root.message
                color: Theme.textPrimary
                font.pixelSize: 13
                wrapMode: Text.WordWrap
                lineHeight: 1.2
            }

            MouseArea {
                Layout.preferredWidth: 20
                Layout.preferredHeight: 20
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                    root.opacity = 0.0;
                    toastCard.y = 20;
                }
                Text {
                    anchors.centerIn: parent
                    text: "✕"
                    color: Theme.textMuted
                    font.pixelSize: 12
                }
            }
        }
    }
}
