import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import QtQuick.Layouts
import QtQuick.Dialogs
import "../components"

ScrollView {
    id: root
    contentWidth: availableWidth
    clip: true

    readonly property color clrCard:       Theme.surfaceCard
    readonly property color clrCardHover:  Theme.surfaceHover
    readonly property color clrCardBorder: Theme.borderCard
    readonly property color clrAccent:     Theme.accentSolid
    readonly property color clrAccentCyan: Theme.isDark ? Theme.accentHover : Theme.accentSolid
    readonly property color clrTxt:        Theme.textPrimary
    readonly property color clrTxt2:       Theme.textSecondary

    function t(key) {
        return (localeManager && localeManager.currentLanguage, localeManager ? localeManager.t(key) : "");
    }

    function tBtn(key) {
        return root.t(key).replace(/&/g, "&&");
    }

    Column {
        width: Math.min(parent.width - 48, 920)
        anchors.horizontalCenter: parent.horizontalCenter
        spacing: 20
        topPadding: 24
        bottomPadding: 40

        // Page Header (DESIGN.md §4: 22px SemiBold textPrimary, 13px textSecondary)
        Column {
            spacing: 6
            IconLabel {
                glyph: Icons.wrench
                iconColor: Theme.accentSolid
                spacing: 10
                alignment: Qt.AlignLeft
                text: root.t("toolbox.title")
                font.pixelSize: 22
                font.bold: true
                color: Theme.textPrimary
            }
            Text {
                text: root.t("toolbox.subtitle")
                font.pixelSize: 13
                color: Theme.textSecondary
            }
        }

        // =====================================================================
        // Card 1: Advanced Font Manager (uGUI + TMP + Custom Font)
        // =====================================================================
        Rectangle {
            width: parent.width
            implicitHeight: fontCol.implicitHeight + 36
            radius: Theme.radiusCard
            color: Theme.surfaceCard
            border.color: Theme.borderCard
            border.width: 1

            property string activePreset: {
                if (appBackend && appBackend.settings && appBackend.settings["font_preset"])
                    return appBackend.settings["font_preset"];
                return "default_arial";
            }
            property string customFontPath: {
                if (appBackend && appBackend.settings && appBackend.settings["custom_font_path"])
                    return appBackend.settings["custom_font_path"];
                return "";
            }
            property string sysFontName: {
                if (appBackend && appBackend.settings && appBackend.settings["tmp_system_font"])
                    return appBackend.settings["tmp_system_font"];
                return "Arial";
            }

            Column {
                id: fontCol
                anchors.top: parent.top
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.margins: 18
                spacing: 14

                // Card Header (DESIGN.md §4: 15px SemiBold textPrimary)
                RowLayout {
                    width: parent.width
                    spacing: 8

                    IconLabel {
                        glyph: Icons.type
                        iconColor: Theme.accentSolid
                        spacing: 8
                        alignment: Qt.AlignLeft
                        text: root.t("toolbox.font_card_title")
                        font.pixelSize: 15
                        font.bold: true
                        color: Theme.textPrimary
                    }
                    Item { Layout.fillWidth: true }

                    // Recommended Badge (DESIGN.md §3.6: height 24px, radius 4px)
                    Rectangle {
                        implicitWidth: recText.implicitWidth + 16
                        implicitHeight: Theme.heightBadge
                        radius: Theme.radiusBadge
                        color: Theme.accentSubtle
                        border.color: Theme.accentBorder
                        border.width: 1

                        Text {
                            id: recText
                            anchors.centerIn: parent
                            text: root.t("toolbox.font_recommended_badge")
                            font.pixelSize: 11
                            font.bold: true
                            color: Theme.isDark ? Theme.accentHover : Theme.accentSolid
                        }
                    }
                }

                Text {
                    text: root.t("toolbox.font_desc")
                    font.pixelSize: 13
                    color: Theme.textSecondary
                    wrapMode: Text.WordWrap
                    width: parent.width
                    lineHeight: 1.3
                }

                // Preset Selector Buttons (DESIGN.md §3.4: radius 6px, height 38px)
                Column {
                    width: parent.width
                    spacing: 8

                    Text {
                        text: root.t("toolbox.font_mode_title")
                        font.pixelSize: 12
                        font.bold: true
                        color: Theme.textSecondary
                    }

                    RowLayout {
                        width: parent.width
                        spacing: 10

                        // Preset 1: Default Arial SDF
                        Button {
                            Accessible.name: root.t("toolbox.font_mode_default")
                            id: btnPresetDefault
                            readonly property bool isSelected: fontCol.parent.activePreset === "default_arial"
                            Layout.fillWidth: true
                            Layout.preferredHeight: 44
                            topInset: 0; bottomInset: 0; leftInset: 0; rightInset: 0; padding: 0
                            scale: down ? 0.98 : 1.0

                            background: Rectangle {
                                radius: Theme.radiusControl
                                color: btnPresetDefault.isSelected ? Theme.accentSubtle : (btnPresetDefault.hovered ? Theme.surfaceHover : Theme.surfaceControl)
                                border.color: btnPresetDefault.isSelected ? (Theme.isNeon ? Theme.accentHover : Theme.accentSolid) : Theme.borderControl
                                border.width: btnPresetDefault.isSelected ? 1.5 : 1
                                Behavior on color { ColorAnimation { duration: 120 } }
                                Behavior on border.color { ColorAnimation { duration: 120 } }
                            }

                            contentItem: RowLayout {
                                spacing: 8
                                anchors.centerIn: parent
                                Icon {
                                    glyph: Icons.packageBox
                                    size: 16
                                    color: btnPresetDefault.isSelected ? (Theme.isDark ? Theme.accentHover : Theme.accentSolid) : (btnPresetDefault.hovered ? Theme.textPrimary : Theme.textSecondary)
                                }
                                Text {
                                    text: root.t("toolbox.font_mode_default")
                                    font.pixelSize: 13
                                    font.bold: btnPresetDefault.isSelected
                                    color: btnPresetDefault.isSelected ? Theme.textPrimary : (btnPresetDefault.hovered ? Theme.textPrimary : Theme.textSecondary)
                                    elide: Text.ElideRight
                                }
                            }

                            onClicked: {
                                fontCol.parent.activePreset = "default_arial";
                                if (appBackend) appBackend.setSetting("font_preset", "default_arial");
                            }
                        }

                        // Preset 2: Custom Font File
                        Button {
                            Accessible.name: root.t("toolbox.font_mode_custom")
                            id: btnPresetCustom
                            readonly property bool isSelected: fontCol.parent.activePreset === "custom_ttf"
                            Layout.fillWidth: true
                            Layout.preferredHeight: 44
                            topInset: 0; bottomInset: 0; leftInset: 0; rightInset: 0; padding: 0
                            scale: down ? 0.98 : 1.0

                            background: Rectangle {
                                radius: Theme.radiusControl
                                color: btnPresetCustom.isSelected ? Theme.accentSubtle : (btnPresetCustom.hovered ? Theme.surfaceHover : Theme.surfaceControl)
                                border.color: btnPresetCustom.isSelected ? (Theme.isNeon ? Theme.accentHover : Theme.accentSolid) : Theme.borderControl
                                border.width: btnPresetCustom.isSelected ? 1.5 : 1
                                Behavior on color { ColorAnimation { duration: 120 } }
                                Behavior on border.color { ColorAnimation { duration: 120 } }
                            }

                            contentItem: RowLayout {
                                spacing: 8
                                anchors.centerIn: parent
                                Icon {
                                    glyph: Icons.folderOpen
                                    size: 16
                                    color: btnPresetCustom.isSelected ? (Theme.isDark ? Theme.accentHover : Theme.accentSolid) : (btnPresetCustom.hovered ? Theme.textPrimary : Theme.textSecondary)
                                }
                                Text {
                                    text: root.t("toolbox.font_mode_custom")
                                    font.pixelSize: 13
                                    font.bold: btnPresetCustom.isSelected
                                    color: btnPresetCustom.isSelected ? Theme.textPrimary : (btnPresetCustom.hovered ? Theme.textPrimary : Theme.textSecondary)
                                    elide: Text.ElideRight
                                }
                            }

                            onClicked: {
                                fontCol.parent.activePreset = "custom_ttf";
                                if (appBackend) appBackend.setSetting("font_preset", "custom_ttf");
                            }
                        }

                        // Preset 3: System Font Override
                        Button {
                            Accessible.name: root.t("toolbox.font_mode_system")
                            id: btnPresetSystem
                            readonly property bool isSelected: fontCol.parent.activePreset === "system_font"
                            Layout.fillWidth: true
                            Layout.preferredHeight: 44
                            topInset: 0; bottomInset: 0; leftInset: 0; rightInset: 0; padding: 0
                            scale: down ? 0.98 : 1.0

                            background: Rectangle {
                                radius: Theme.radiusControl
                                color: btnPresetSystem.isSelected ? Theme.accentSubtle : (btnPresetSystem.hovered ? Theme.surfaceHover : Theme.surfaceControl)
                                border.color: btnPresetSystem.isSelected ? (Theme.isNeon ? Theme.accentHover : Theme.accentSolid) : Theme.borderControl
                                border.width: btnPresetSystem.isSelected ? 1.5 : 1
                                Behavior on color { ColorAnimation { duration: 120 } }
                                Behavior on border.color { ColorAnimation { duration: 120 } }
                            }

                            contentItem: RowLayout {
                                spacing: 8
                                anchors.centerIn: parent
                                Icon {
                                    glyph: Icons.type
                                    size: 16
                                    color: btnPresetSystem.isSelected ? (Theme.isDark ? Theme.accentHover : Theme.accentSolid) : (btnPresetSystem.hovered ? Theme.textPrimary : Theme.textSecondary)
                                }
                                Text {
                                    text: root.t("toolbox.font_mode_system")
                                    font.pixelSize: 13
                                    font.bold: btnPresetSystem.isSelected
                                    color: btnPresetSystem.isSelected ? Theme.textPrimary : (btnPresetSystem.hovered ? Theme.textPrimary : Theme.textSecondary)
                                    elide: Text.ElideRight
                                }
                            }

                            onClicked: {
                                fontCol.parent.activePreset = "system_font";
                                if (appBackend) appBackend.setSetting("font_preset", "system_font");
                            }
                        }
                    }
                }

                // Custom font picker area
                Column {
                    width: parent.width
                    spacing: 6
                    visible: fontCol.parent.activePreset === "custom_ttf"

                    Text {
                        text: root.t("toolbox.font_custom_path_label")
                        font.pixelSize: 12
                        color: Theme.textSecondary
                    }

                    RowLayout {
                        width: parent.width
                        spacing: 10

                        TextField {
                            id: customFontPathInput
                            Layout.fillWidth: true
                            Layout.preferredHeight: Theme.heightInput
                            text: fontCol.parent.customFontPath
                            placeholderText: "Arial"
                            color: Theme.textPrimary
                            placeholderTextColor: Theme.textMuted
                            background: Rectangle {
                                radius: Theme.radiusControl
                                color: Theme.surfaceControl
                                border.color: customFontPathInput.activeFocus ? Theme.borderFocus : Theme.borderControl
                                border.width: 1
                            }
                            onTextChanged: fontCol.parent.customFontPath = text
                        }

                        Button {
                            Accessible.name: root.t("toolbox.font_custom_browse_btn")
                            id: btnBrowseFont
                            Layout.preferredHeight: Theme.heightInput
                            topInset: 0; bottomInset: 0; leftInset: 0; rightInset: 0; padding: 0
                            scale: down ? 0.98 : 1.0
                            background: Rectangle {
                                radius: Theme.radiusControl
                                color: btnBrowseFont.hovered ? Theme.surfaceHover : Theme.surfaceControl
                                border.color: btnBrowseFont.hovered ? Theme.borderFocus : Theme.borderControl
                                border.width: 1
                            }
                            contentItem: RowLayout {
                                spacing: 6
                                anchors.centerIn: parent
                                Icon { glyph: Icons.folderOpen; size: 14; color: btnBrowseFont.hovered ? Theme.textPrimary : Theme.textSecondary }
                                Text {
                                    text: root.t("toolbox.font_custom_browse_btn")
                                    font.pixelSize: 13
                                    color: btnBrowseFont.hovered ? Theme.textPrimary : Theme.textSecondary
                                }
                            }
                            onClicked: customFontDialog.open()
                        }
                    }
                }

                // System font input area
                Column {
                    width: parent.width
                    spacing: 6
                    visible: fontCol.parent.activePreset === "system_font"

                    Text {
                        text: root.t("settings.tmp_system_font_label")
                        font.pixelSize: 12
                        color: Theme.textSecondary
                    }

                    TextField {
                        id: systemFontNameInput
                        width: Math.min(parent.width, 360)
                        height: Theme.heightInput
                        text: fontCol.parent.sysFontName
                        placeholderText: "Arial"
                        color: Theme.textPrimary
                        placeholderTextColor: Theme.textMuted
                        background: Rectangle {
                            radius: Theme.radiusControl
                            color: Theme.surfaceControl
                            border.color: systemFontNameInput.activeFocus ? Theme.borderFocus : Theme.borderControl
                            border.width: 1
                        }
                        onTextChanged: fontCol.parent.sysFontName = text
                    }
                }

                // Active Font Status Summary (DESIGN.md §3.5: InfoBanner — KESİNLİKLE saf beyaz kullanılmaz)
                Rectangle {
                    width: parent.width
                    implicitHeight: 36
                    radius: Theme.radiusControl
                    color: Theme.surfaceSubtle
                    border.color: Theme.borderCard
                    border.width: 1

                    // Sol kenar vurgu göstergesi
                    Rectangle {
                        anchors.left: parent.left
                        anchors.top: parent.top
                        anchors.bottom: parent.bottom
                        width: 3
                        radius: 1.5
                        color: Theme.accentSolid
                    }

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 14
                        anchors.rightMargin: 12
                        spacing: 8

                        Text {
                            text: "ℹ️"
                            font.pixelSize: 13
                        }
                        Text {
                            text: root.t("toolbox.font_status_current") + ":"
                            font.pixelSize: 12
                            color: Theme.textSecondary
                        }
                        Text {
                            text: {
                                var p = fontCol.parent.activePreset;
                                if (p === "custom_ttf") return root.t("toolbox.font_mode_custom") + " (" + (fontCol.parent.customFontPath ? fontCol.parent.customFontPath.split(/[\\/]/).pop() : "Arial") + ")";
                                if (p === "system_font") return root.t("toolbox.font_mode_system") + " (" + fontCol.parent.sysFontName + ")";
                                return root.t("toolbox.font_mode_default");
                            }
                            font.pixelSize: 12
                            font.bold: true
                            color: Theme.textPrimary
                            Layout.fillWidth: true
                            elide: Text.ElideRight
                        }
                    }
                }

                // Apply Font CTA Button (DESIGN.md §3.2 PrimaryCTA: radius 6px, height 42px)
                Button {
                    Accessible.name: root.tBtn("toolbox.font_apply_btn")
                    id: btnApplyFont
                    width: parent.width
                    implicitHeight: 44
                    topInset: 0; bottomInset: 0; leftInset: 0; rightInset: 0; padding: 0
                    enabled: Boolean(appBackend && appBackend.gamePath && !appBackend.isBusy)
                    scale: down ? 0.98 : (hovered ? 1.01 : 1.0)
                    Behavior on scale { NumberAnimation { duration: 120 } }

                    background: Rectangle {
                        radius: Theme.radiusControl
                        color: {
                            if (!btnApplyFont.enabled) return Theme.surfaceDisabled;
                            if (Theme.isNeon) {
                                return btnApplyFont.down ? Theme.accentAlpha(0.45) : (btnApplyFont.hovered ? Theme.accentAlpha(0.35) : Theme.accentAlpha(0.25));
                            }
                            return btnApplyFont.down ? Theme.accentSolid : (btnApplyFont.hovered ? Theme.accentHover : Theme.accentSolid);
                        }
                        border.color: {
                            if (!btnApplyFont.enabled) return "transparent";
                            if (Theme.isNeon) return btnApplyFont.hovered ? Theme.accentHover : Theme.accentAlpha(0.8);
                            return "transparent";
                        }
                        border.width: Theme.isNeon ? 1.5 : 0
                        opacity: btnApplyFont.enabled ? 1.0 : 0.5
                    }

                    contentItem: RowLayout {
                        spacing: 8
                        anchors.centerIn: parent
                        Icon {
                            glyph: Icons.sparkles
                            size: 16
                            color: btnApplyFont.enabled ? Theme.accentContrastText : Theme.textMuted
                        }
                        Text {
                            text: root.tBtn("toolbox.font_apply_btn")
                            font.pixelSize: 14
                            font.bold: true
                            color: {
                                if (!btnApplyFont.enabled) return Theme.textMuted;
                                if (Theme.isNeon) return Theme.textPrimary;
                                return Theme.accentContrastText;
                            }
                        }
                    }

                    onClicked: {
                        if (appBackend) {
                            appBackend.applyFontConfiguration(
                                fontCol.parent.activePreset,
                                fontCol.parent.customFontPath,
                                fontCol.parent.sysFontName
                            );
                        }
                    }
                }
            }
        }

        // =====================================================================
        // Card 2: BepInEx Modding
        // =====================================================================
        Rectangle {
            width: parent.width
            implicitHeight: bepCol.implicitHeight + 36
            radius: Theme.radiusCard
            color: Theme.surfaceCard
            border.color: Theme.borderCard
            border.width: 1

            Column {
                id: bepCol
                anchors.top: parent.top
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.margins: 18
                spacing: 12

                RowLayout {
                    width: parent.width
                    spacing: 8

                    Icon { glyph: Icons.packageBox; size: 18; color: Theme.accentSolid }

                    Text {
                        text: root.t("toolbox.bepinex_card_title")
                        font.pixelSize: 15
                        font.bold: true
                        color: Theme.textPrimary
                    }
                    Item { Layout.fillWidth: true }

                    // BepInEx Status Rozeti (DESIGN.md §3.6: radius 4px, height 24px)
                    Rectangle {
                        implicitWidth: hookStatusTxt.implicitWidth + 16
                        implicitHeight: Theme.heightBadge
                        radius: Theme.radiusBadge
                        color: (appBackend && appBackend.hasBepInEx) ? Theme.statusSuccessSubtle : Theme.statusWarningSubtle
                        border.color: (appBackend && appBackend.hasBepInEx) ? Theme.statusSuccessBorder : Theme.statusWarningBorder
                        border.width: 1

                        Text {
                            id: hookStatusTxt
                            anchors.centerIn: parent
                            text: (appBackend && appBackend.hasBepInEx)
                                  ? root.t("dashboard.bepinex_active")
                                  : root.t("dashboard.vanilla")
                            font.pixelSize: 11
                            font.bold: true
                            color: (appBackend && appBackend.hasBepInEx) ? Theme.statusSuccess : Theme.statusWarning
                        }
                    }
                }

                Text {
                    text: root.t("toolbox.bepinex_desc")
                    font.pixelSize: 13
                    color: Theme.textSecondary
                    wrapMode: Text.WordWrap
                    width: parent.width
                    lineHeight: 1.3
                }

                RowLayout {
                    spacing: 12

                    // Uninstall BepInEx Button (Destructive - DESIGN.md §3.3)
                    Button {
                        Accessible.name: root.t("toolbox.uninstall_bepinex_btn")
                        id: btnUninstallBep
                        implicitHeight: Theme.heightSecondary
                        topInset: 0; bottomInset: 0; leftInset: 0; rightInset: 0; padding: 0
                        enabled: Boolean(appBackend && appBackend.gamePath && !appBackend.isBusy && appBackend.hasBepInEx)
                        scale: down ? 0.98 : 1.0

                        background: Rectangle {
                            radius: Theme.radiusControl
                            color: btnUninstallBep.enabled ? (btnUninstallBep.hovered ? Theme.statusDangerSubtle : Theme.surfaceControl) : Theme.surfaceControl
                            border.color: btnUninstallBep.enabled ? (btnUninstallBep.hovered ? Theme.statusDanger : Theme.statusDangerBorder) : Theme.borderControl
                            border.width: 1
                            opacity: btnUninstallBep.enabled ? 1.0 : 0.4
                        }

                        contentItem: RowLayout {
                            spacing: 8
                            anchors.centerIn: parent
                            Icon {
                                glyph: Icons.trash2
                                size: 14
                                color: btnUninstallBep.enabled ? Theme.statusDanger : Theme.textMuted
                            }
                            Text {
                                text: root.t("toolbox.uninstall_bepinex_btn")
                                font.pixelSize: 13
                                font.bold: true
                                color: btnUninstallBep.enabled ? Theme.statusDanger : Theme.textMuted
                            }
                        }

                        onClicked: {
                            if (appBackend) appBackend.uninstallHooks();
                        }
                    }
                }
            }
        }

        // =====================================================================
        // Card 3: Static Binary & Asset Harvester
        // =====================================================================
        Rectangle {
            width: parent.width
            implicitHeight: harvCol.implicitHeight + 36
            radius: Theme.radiusCard
            color: Theme.surfaceCard
            border.color: Theme.borderCard
            border.width: 1

            Column {
                id: harvCol
                anchors.top: parent.top
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.margins: 18
                spacing: 14

                RowLayout {
                    width: parent.width
                    spacing: 8

                    IconLabel {
                        glyph: Icons.scanSearch
                        iconColor: Theme.accentSolid
                        spacing: 8
                        alignment: Qt.AlignLeft
                        text: root.t("toolbox.harvester_card_title")
                        font.pixelSize: 15
                        font.bold: true
                        color: Theme.textPrimary
                    }
                    Item { Layout.fillWidth: true }

                    // Harvested Lines Sayaç Rozeti (DESIGN.md §3.6 Nötr Rozet: surfaceControl + borderControl, radius 4px)
                    Rectangle {
                        implicitWidth: harvestBadge.implicitWidth + 16
                        implicitHeight: Theme.heightBadge
                        radius: Theme.radiusBadge
                        color: Theme.surfaceControl
                        border.color: Theme.borderControl
                        border.width: 1

                        Text {
                            id: harvestBadge
                            anchors.centerIn: parent
                            text: root.t("toolbox.harvester_badge").replace("{count}", appBackend ? appBackend.harvestCount : 0)
                            font.pixelSize: 11
                            font.weight: Font.Medium
                            color: Theme.textSecondary
                        }
                    }
                }

                Text {
                    text: root.t("toolbox.harvester_desc")
                    font.pixelSize: 13
                    color: Theme.textSecondary
                    wrapMode: Text.WordWrap
                    width: parent.width
                    lineHeight: 1.3
                }

                Flow {
                    width: parent.width
                    spacing: 10

                    // Harvester Action Button 1: Metadata
                    Button {
                        Accessible.name: root.t("toolbox.harvest_metadata_btn")
                        id: btnHarvMeta
                        implicitHeight: Theme.heightSecondary
                        topInset: 0; bottomInset: 0; leftInset: 0; rightInset: 0; padding: 0
                        enabled: Boolean(appBackend && appBackend.gamePath && !appBackend.isBusy)
                        scale: down ? 0.98 : 1.0

                        background: Rectangle {
                            radius: Theme.radiusControl
                            color: btnHarvMeta.hovered ? Theme.surfaceHover : Theme.surfaceControl
                            border.color: btnHarvMeta.hovered ? Theme.borderFocus : Theme.borderControl
                            border.width: 1
                            opacity: btnHarvMeta.enabled ? 1.0 : 0.5
                        }

                        contentItem: RowLayout {
                            spacing: 8
                            anchors.centerIn: parent
                            Icon {
                                glyph: Icons.search
                                size: 14
                                color: btnHarvMeta.enabled ? (btnHarvMeta.hovered ? Theme.textPrimary : Theme.textSecondary) : Theme.textMuted
                            }
                            Text {
                                text: root.t("toolbox.harvest_metadata_btn")
                                font.pixelSize: 13
                                color: btnHarvMeta.enabled ? (btnHarvMeta.hovered ? Theme.textPrimary : Theme.textSecondary) : Theme.textMuted
                            }
                        }

                        onClicked: {
                            if (appBackend) appBackend.harvestMetadata();
                        }
                    }

                    // Harvester Action Button 2: Assembly
                    Button {
                        Accessible.name: root.t("toolbox.harvest_assembly_btn")
                        id: btnHarvAsm
                        implicitHeight: Theme.heightSecondary
                        topInset: 0; bottomInset: 0; leftInset: 0; rightInset: 0; padding: 0
                        enabled: Boolean(appBackend && appBackend.gamePath && !appBackend.isBusy)
                        scale: down ? 0.98 : 1.0

                        background: Rectangle {
                            radius: Theme.radiusControl
                            color: btnHarvAsm.hovered ? Theme.surfaceHover : Theme.surfaceControl
                            border.color: btnHarvAsm.hovered ? Theme.borderFocus : Theme.borderControl
                            border.width: 1
                            opacity: btnHarvAsm.enabled ? 1.0 : 0.5
                        }

                        contentItem: RowLayout {
                            spacing: 8
                            anchors.centerIn: parent
                            Icon {
                                glyph: Icons.settings
                                size: 14
                                color: btnHarvAsm.enabled ? (btnHarvAsm.hovered ? Theme.textPrimary : Theme.textSecondary) : Theme.textMuted
                            }
                            Text {
                                text: root.t("toolbox.harvest_assembly_btn")
                                font.pixelSize: 13
                                color: btnHarvAsm.enabled ? (btnHarvAsm.hovered ? Theme.textPrimary : Theme.textSecondary) : Theme.textMuted
                            }
                        }

                        onClicked: {
                            if (appBackend) appBackend.harvestAssembly();
                        }
                    }

                    // Harvester Action Button 3: StreamingAssets
                    Button {
                        Accessible.name: root.t("toolbox.harvest_streaming_btn")
                        id: btnHarvStream
                        implicitHeight: Theme.heightSecondary
                        topInset: 0; bottomInset: 0; leftInset: 0; rightInset: 0; padding: 0
                        enabled: Boolean(appBackend && appBackend.gamePath && !appBackend.isBusy)
                        scale: down ? 0.98 : 1.0

                        background: Rectangle {
                            radius: Theme.radiusControl
                            color: btnHarvStream.hovered ? Theme.surfaceHover : Theme.surfaceControl
                            border.color: btnHarvStream.hovered ? Theme.borderFocus : Theme.borderControl
                            border.width: 1
                            opacity: btnHarvStream.enabled ? 1.0 : 0.5
                        }

                        contentItem: RowLayout {
                            spacing: 8
                            anchors.centerIn: parent
                            Icon {
                                glyph: Icons.folderOpen
                                size: 14
                                color: btnHarvStream.enabled ? (btnHarvStream.hovered ? Theme.textPrimary : Theme.textSecondary) : Theme.textMuted
                            }
                            Text {
                                text: root.t("toolbox.harvest_streaming_btn")
                                font.pixelSize: 13
                                color: btnHarvStream.enabled ? (btnHarvStream.hovered ? Theme.textPrimary : Theme.textSecondary) : Theme.textMuted
                            }
                        }

                        onClicked: {
                            if (appBackend) appBackend.harvestStreamingAssets();
                        }
                    }

                    // Harvester Action Button 4: Assets
                    Button {
                        Accessible.name: root.tBtn("toolbox.harvest_assets_btn")
                        id: btnHarvAssets
                        implicitHeight: Theme.heightSecondary
                        topInset: 0; bottomInset: 0; leftInset: 0; rightInset: 0; padding: 0
                        enabled: Boolean(appBackend && appBackend.gamePath && !appBackend.isBusy)
                        scale: down ? 0.98 : 1.0

                        background: Rectangle {
                            radius: Theme.radiusControl
                            color: btnHarvAssets.hovered ? Theme.surfaceHover : Theme.surfaceControl
                            border.color: btnHarvAssets.hovered ? Theme.borderFocus : Theme.borderControl
                            border.width: 1
                            opacity: btnHarvAssets.enabled ? 1.0 : 0.5
                        }

                        contentItem: RowLayout {
                            spacing: 8
                            anchors.centerIn: parent
                            Icon {
                                glyph: Icons.packageBox
                                size: 14
                                color: btnHarvAssets.enabled ? (btnHarvAssets.hovered ? Theme.textPrimary : Theme.textSecondary) : Theme.textMuted
                            }
                            Text {
                                text: root.tBtn("toolbox.harvest_assets_btn")
                                font.pixelSize: 13
                                color: btnHarvAssets.enabled ? (btnHarvAssets.hovered ? Theme.textPrimary : Theme.textSecondary) : Theme.textMuted
                            }
                        }

                        onClicked: {
                            if (appBackend) appBackend.harvestAssets();
                        }
                    }
                }
            }
        }
    }

    FileDialog {
        id: customFontDialog
        title: root.t("toolbox.font_select_dialog_title")
        nameFilters: ["Font / TrueType / OpenType (*.ttf *.otf)"]
        onAccepted: {
            customFontPathInput.text = selectedFile;
        }
    }
}
