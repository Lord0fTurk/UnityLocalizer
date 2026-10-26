import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import QtQuick.Layouts
import "../components"

Popup {
    id: root
    modal: true
    focus: true
    anchors.centerIn: parent
    width: Math.min(parent.width - 48, 680)
    padding: 20
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

    property var summary: null

    function safeNum(val) {
        if (val === undefined || val === null || isNaN(val)) return 0;
        return Number(val);
    }

    function safeStr(val, fallback) {
        if (val === undefined || val === null) return fallback || "";
        return String(val);
    }

    signal openEditorRequested()

    function openWithSummary(data) {
        summary = data;
        open();
    }

    function t(key) {
        return (localeManager && localeManager.currentLanguage, localeManager ? localeManager.t(key) : "");
    }

    background: Rectangle {
        radius: Theme.radiusCard
        color: Theme.surfaceCard
        border.color: Theme.borderCard
        border.width: 1

        Rectangle {
            z: -1
            anchors.fill: parent
            anchors.margins: -2
            radius: Theme.radiusCard + 2
            color: "transparent"
            border.color: Theme.isNeon ? Theme.accentAlpha(0.35) : "transparent"
            border.width: 1
        }
    }

    // Padding (not anchors) keeps the popup's implicit size in sync with its content.
    contentItem: ColumnLayout {
        spacing: 16

        // 1. Header with Celebration Badge & Close button
        RowLayout {
            Layout.fillWidth: true
            spacing: 14

            Rectangle {
                Layout.preferredWidth: 44
                Layout.preferredHeight: 44
                radius: Theme.radiusControl + 2
                color: Theme.statusSuccessSubtle
                border.color: Theme.statusSuccessBorder
                border.width: 1

                Icon {
                    anchors.centerIn: parent
                    glyph: Icons.partyPopper
                    size: 22
                    color: Theme.statusSuccess
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 3

                Text {
                    text: root.t("dashboard.completion_title")
                    font.pixelSize: 17
                    font.bold: true
                    color: Theme.textPrimary
                }

                Text {
                    text: root.t("dashboard.completion_subtitle")
                    font.pixelSize: 12
                    color: Theme.textSecondary
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }
            }

            // Close button
            Button {
                implicitWidth: 30
                implicitHeight: 30
                topInset: 0; bottomInset: 0; leftInset: 0; rightInset: 0; padding: 0
                background: Rectangle {
                    radius: Theme.radiusBadge
                    color: parent.hovered ? Theme.surfaceHover : "transparent"
                }
                contentItem: Icon {
                    anchors.centerIn: parent
                    glyph: Icons.x
                    size: 16
                    color: parent.parent.hovered ? Theme.textPrimary : Theme.textMuted
                }
                onClicked: root.close()
            }
        }

        // 2. Metrics 4-Box Grid
        GridLayout {
            Layout.fillWidth: true
            columns: 2
            rowSpacing: 10
            columnSpacing: 10
            uniformCellWidths: true

            // Metric 1: Translated Lines
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: 56
                radius: Theme.radiusControl
                color: Theme.surfaceControl
                border.color: Theme.borderControl
                border.width: 1

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 10
                    spacing: 10

                    Icon { glyph: Icons.languages; size: 18; color: Theme.accentSolid }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2
                        Text { text: root.t("dashboard.completion_stat_translated"); font.pixelSize: 11; color: Theme.textSecondary }
                        Text { text: root.safeNum(root.summary ? root.summary.translated_count : 0).toLocaleString(); font.pixelSize: 15; font.bold: true; color: Theme.textPrimary }
                    }
                }
            }

            // Metric 2: Success Rate
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: 56
                radius: Theme.radiusControl
                color: Theme.surfaceControl
                border.color: Theme.borderControl
                border.width: 1

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 10
                    spacing: 10

                    Icon { glyph: Icons.circleCheck; size: 18; color: Theme.statusSuccess }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2
                        Text { text: root.t("dashboard.completion_stat_success"); font.pixelSize: 11; color: Theme.textSecondary }
                        Text { text: root.safeStr(root.summary ? root.summary.success_rate : null, "100%"); font.pixelSize: 15; font.bold: true; color: Theme.statusSuccess }
                    }
                }
            }

            // Metric 3: Total Harvested
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: 56
                radius: Theme.radiusControl
                color: Theme.surfaceControl
                border.color: Theme.borderControl
                border.width: 1

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 10
                    spacing: 10

                    Icon { glyph: Icons.database; size: 18; color: Theme.textSecondary }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2
                        Text { text: root.t("dashboard.completion_stat_total"); font.pixelSize: 11; color: Theme.textSecondary }
                        Text { text: root.safeNum(root.summary ? root.summary.total_harvested : 0).toLocaleString(); font.pixelSize: 15; font.bold: true; color: Theme.textPrimary }
                    }
                }
            }

            // Metric 4: Target Language
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: 56
                radius: Theme.radiusControl
                color: Theme.surfaceControl
                border.color: Theme.borderControl
                border.width: 1

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 10
                    spacing: 10

                    Icon { glyph: Icons.globe; size: 18; color: Theme.textSecondary }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2
                        Text { text: root.t("dashboard.completion_stat_target"); font.pixelSize: 11; color: Theme.textSecondary }
                        Text { text: root.safeStr(root.summary ? root.summary.target_lang : null, "").toUpperCase(); font.pixelSize: 15; font.bold: true; color: Theme.isDark ? Theme.accentHover : Theme.accentSolid }
                    }
                }
            }
        }

        // 3. Destination Path Bar
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 36
            radius: Theme.radiusControl
            color: Theme.surfaceSubtle
            border.color: Theme.borderControl
            border.width: 1

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 12
                anchors.rightMargin: 12
                spacing: 8

                Icon { glyph: Icons.folder; size: 13; color: Theme.textSecondary }
                Text {
                    Layout.fillWidth: true
                    text: root.safeStr(root.summary ? root.summary.game_path : null, "")
                    font.pixelSize: 11
                    color: Theme.textSecondary
                    elide: Text.ElideMiddle
                }
            }
        }

        // 3b. Support prompt: only from the 3rd finished run, and never again once dismissed
        Rectangle {
            Layout.fillWidth: true
            visible: Boolean(root.summary && root.summary.show_support)
            implicitHeight: supportCol.implicitHeight + 20
            radius: Theme.radiusControl
            color: Qt.rgba(244/255, 114/255, 182/255, 0.07)
            border.color: Qt.rgba(244/255, 114/255, 182/255, 0.35)
            border.width: 1

            ColumnLayout {
                id: supportCol
                anchors.fill: parent
                anchors.margins: 10
                spacing: 6

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10

                    Icon { glyph: Icons.heart; size: 16; color: "#F472B6" }
                    Text {
                        Layout.fillWidth: true
                        text: root.t("dashboard.completion_support_text")
                        font.pixelSize: 12
                        color: Theme.textSecondary
                        wrapMode: Text.WordWrap
                    }
                    Button {
                        id: supportBtn
                        implicitHeight: 28
                        implicitWidth: supportLabel.implicitWidth + 24
                        topInset: 0; bottomInset: 0; leftInset: 0; rightInset: 0; padding: 0
                        background: Rectangle {
                            radius: Theme.radiusControl
                            color: Qt.rgba(244/255, 114/255, 182/255, supportBtn.hovered ? 0.28 : 0.16)
                            border.color: Qt.rgba(244/255, 114/255, 182/255, 0.6)
                            border.width: 1
                        }
                        contentItem: Text {
                            id: supportLabel
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                            text: root.t("dashboard.completion_support_btn")
                            font.pixelSize: 11
                            font.bold: true
                            color: "#F472B6"
                        }
                        onClicked: Qt.openUrlExternally("https://www.patreon.com/cw/LordOfTurk")
                    }
                }

                CheckBox {
                    id: hideSupport
                    text: root.t("dashboard.completion_support_hide")
                    font.pixelSize: 11
                    padding: 0
                    onToggled: { if (appBackend) appBackend.setSetting("hide_support_prompt", checked); }
                }
            }
        }

        // 4. Action Buttons Row
        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            ActionButton {
                id: btnLaunch
                visible: Boolean(root.summary && root.summary.has_exe)
                glyph: Icons.play
                label: root.t("dashboard.completion_launch_game")
                filled: true
                fillColor: Theme.statusSuccess
                onClicked: { if (appBackend) appBackend.launchGame(); }
            }

            ActionButton {
                id: btnReview
                glyph: Icons.squarePen
                label: root.t("dashboard.completion_review_editor")
                onClicked: {
                    root.close();
                    root.openEditorRequested();
                }
            }

            ActionButton {
                id: btnFolder
                glyph: Icons.folderOpen
                label: root.t("dashboard.completion_open_folder")
                onClicked: { if (appBackend) appBackend.openGameFolder(); }
            }

            ActionButton {
                id: btnDone
                glyph: Icons.circleCheck
                label: root.t("dashboard.completion_close")
                filled: true
                onClicked: root.close()
            }
        }
    }

    // Action button that never exceeds its layout slot: it shares row space with its
    // siblings and elides its label instead of overflowing the dialog.
    component ActionButton: Button {
        id: btn
        property string glyph: ""
        property string label: ""
        property bool filled: false
        property color fillColor: Theme.accentSolid

        Layout.fillWidth: true
        Layout.preferredWidth: implicitWidth
        Layout.minimumWidth: 0
        implicitHeight: Theme.heightSecondary
        implicitWidth: row.implicitWidth + 28
        topInset: 0; bottomInset: 0; leftInset: 0; rightInset: 0; padding: 0
        scale: down ? 0.98 : 1.0

        background: Rectangle {
            radius: Theme.radiusControl
            color: btn.filled
                ? ((btn.hovered && !btn.down) ? Theme.accentHover : btn.fillColor)
                : (btn.hovered ? Theme.surfaceHover : Theme.surfaceControl)
            border.color: btn.filled ? "transparent" : (btn.hovered ? Theme.borderFocus : Theme.borderControl)
            border.width: btn.filled ? 0 : 1
        }

        contentItem: Item {
            RowLayout {
                id: row
                anchors.centerIn: parent
                width: Math.min(implicitWidth, parent.width - 16)
                spacing: 6

                Icon {
                    glyph: btn.glyph
                    size: 13
                    color: btn.filled ? Theme.accentContrastText : (btn.hovered ? Theme.textPrimary : Theme.textSecondary)
                }
                Text {
                    Layout.fillWidth: true
                    text: btn.label
                    textFormat: Text.PlainText
                    elide: Text.ElideRight
                    font.pixelSize: 12
                    font.bold: btn.filled
                    color: btn.filled ? Theme.accentContrastText : (btn.hovered ? Theme.textPrimary : Theme.textSecondary)
                }
            }
        }
    }
}
