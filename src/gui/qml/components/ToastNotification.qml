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
    Behavior on opacity { NumberAnimation { duration: 200 } }

    property string message: ""
    property string toastType: "info" // "success", "error", "warning", "info"

    // Screen readers announce the toast as an alert with its message.
    Accessible.role: Accessible.AlertMessage
    Accessible.name: message

    function show(msg, type) {
        message = msg;
        toastType = type || "info";
        // Errors and warnings stay long enough to be read; the timer also pauses on hover.
        dismissTimer.interval = (toastType === "error" || toastType === "warning") ? 10000 : 4000;
        root.opacity = 1.0;
        toastCard.y = 0;
        dismissTimer.restart();
    }

    function dismiss() {
        dismissTimer.stop();
        root.opacity = 0.0;
        toastCard.y = 20;
    }

    Timer {
        id: dismissTimer
        interval: 4000
        onTriggered: root.dismiss()
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

        HoverHandler {
            onHoveredChanged: {
                if (hovered) dismissTimer.stop();
                else if (root.opacity > 0) dismissTimer.restart();
            }
        }

        RowLayout {
            id: contentRow
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: 14
            spacing: 12

            Icon {
                glyph: {
                    if (toastType === "success") return Icons.circleCheck;
                    if (toastType === "error") return Icons.circleX;
                    if (toastType === "warning") return Icons.triangleAlert;
                    return Icons.info;
                }
                color: {
                    if (toastType === "success") return Theme.statusSuccess;
                    if (toastType === "error") return Theme.statusDanger;
                    if (toastType === "warning") return Theme.statusWarning;
                    return Theme.accentSolid;
                }
                size: 20
            }

            Text {
                Layout.fillWidth: true
                text: root.message
                color: Theme.textPrimary
                font.pixelSize: 13
                wrapMode: Text.WordWrap
                lineHeight: 1.2
            }

            Button {
                id: closeButton
                Layout.preferredWidth: 28
                Layout.preferredHeight: 28
                Layout.alignment: Qt.AlignTop
                topInset: 0; bottomInset: 0; leftInset: 0; rightInset: 0; padding: 0
                Accessible.name: localeManager ? localeManager.t("common.close") : ""
                onClicked: root.dismiss()

                background: Rectangle {
                    radius: Theme.radiusBadge
                    color: closeButton.hovered ? Theme.surfaceHover : "transparent"
                }
                contentItem: Item {
                    Icon {
                        anchors.centerIn: parent
                        glyph: Icons.x
                        color: closeButton.hovered ? Theme.textPrimary : Theme.textSecondary
                        size: 14
                    }
                }
            }
        }
    }
}
