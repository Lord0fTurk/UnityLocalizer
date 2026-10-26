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

    // Asks Main.qml to switch to the review editor tab.
    signal openEditorRequested()

    // Theme token references
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

    function getGameName(path) {
        if (!path) return "";
        var clean = ("" + path).replace(/[\\\/]+$/, "");
        var parts = clean.split(/[\\\/]/);
        return parts.length > 0 ? parts[parts.length - 1] : clean;
    }

    Column {
        width: Math.min(parent.width - 48, 920)
        anchors.horizontalCenter: parent.horizontalCenter
        spacing: 20
        topPadding: 24
        bottomPadding: 40

        // 1. Header (DESIGN.md §4: 22px SemiBold textPrimary)
        Column {
            spacing: 6
            Text {
                text: root.t("dashboard.title")
                font.pixelSize: 22
                font.bold: true
                color: Theme.textPrimary
            }
            Text {
                text: root.t("dashboard.subtitle")
                font.pixelSize: 13
                color: Theme.textSecondary
            }
        }

        // 2. Game Selection Drop Zone Card
        Rectangle {
            id: dropCard
            width: parent.width
            readonly property bool hasGame: Boolean(appBackend && appBackend.gamePath)
            implicitHeight: hasGame ? (selectedGameLayout.implicitHeight + 36) : 160
            radius: Theme.radiusCard
            color: dragArea.containsDrag ? Theme.accentSubtle : (dropMouseArea.containsMouse && !hasGame ? clrCardHover : clrCard)
            border.color: dragArea.containsDrag ? Theme.accentHover : (dropMouseArea.containsMouse && !hasGame ? Theme.accentAlpha(0.5) : clrCardBorder)
            border.width: dragArea.containsDrag ? 2 : 1

            Behavior on color { ColorAnimation { duration: 150 } }
            Behavior on border.color { ColorAnimation { duration: 150 } }

            DropArea {
                id: dragArea
                anchors.fill: parent
                onDropped: (drop) => {
                    if (drop.hasUrls && drop.urls.length > 0 && appBackend) {
                        appBackend.selectGame(drop.urls[0]);
                    }
                }
            }

            MouseArea {
                id: dropMouseArea
                anchors.fill: parent
                enabled: !dropCard.hasGame
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: folderDialog.open()
            }

            // A) EMPTY STATE (Oyun seçilmediğinde)
            ColumnLayout {
                id: emptyDropLayout
                visible: !dropCard.hasGame
                anchors.centerIn: parent
                spacing: 12
                width: parent.width - 48

                Rectangle {
                    Layout.alignment: Qt.AlignHCenter
                    width: 52
                    height: 52
                    radius: 26
                    color: Theme.accentSubtle
                    border.color: Theme.accentBorder
                    border.width: 1

                    Icon {
                        anchors.centerIn: parent
                        glyph: Icons.folderOpen
                        size: 24
                        color: Theme.accentSolid
                    }
                }

                Text {
                    Layout.alignment: Qt.AlignHCenter
                    text: root.t("dashboard.drag_drop_hint")
                    font.pixelSize: 14
                    font.bold: true
                    color: Theme.textPrimary
                    horizontalAlignment: Text.AlignHCenter
                }

                Button {
                    id: btnSelectGameEmpty
                    Layout.alignment: Qt.AlignHCenter
                    implicitHeight: Theme.heightSecondary
                    implicitWidth: Math.max(160, selectGameEmptyContent.implicitWidth + 32)
                    topInset: 0; bottomInset: 0; leftInset: 0; rightInset: 0; padding: 0
                    scale: down ? 0.98 : 1.0

                    background: Rectangle {
                        radius: Theme.radiusControl
                        color: btnSelectGameEmpty.down ? Theme.accentSolid : (btnSelectGameEmpty.hovered ? Theme.accentHover : Theme.accentSolid)
                        border.width: 0
                        Behavior on color { ColorAnimation { duration: 120 } }
                    }

                    contentItem: RowLayout {
                        id: selectGameEmptyContent
                        spacing: 8
                        anchors.centerIn: parent
                        Icon {
                            glyph: Icons.folderOpen
                            size: 14
                            color: Theme.accentContrastText
                        }
                        Text {
                            text: root.t("dashboard.select_game_btn")
                            font.pixelSize: 13
                            font.bold: true
                            color: Theme.accentContrastText
                        }
                    }

                    onClicked: folderDialog.open()
                }
            }

            // B) SELECTED STATE (Oyun seçildiğinde)
            RowLayout {
                id: selectedGameLayout
                visible: dropCard.hasGame
                anchors.fill: parent
                anchors.margins: 18
                spacing: 16

                // Game Icon Avatar Badge
                Rectangle {
                    Layout.preferredWidth: 48
                    Layout.preferredHeight: 48
                    radius: Theme.radiusControl + 2
                    color: Theme.accentSubtle
                    border.color: Theme.accentBorder
                    border.width: 1

                    Icon {
                        anchors.centerIn: parent
                        glyph: Icons.gamepad2
                        size: 22
                        color: Theme.accentSolid
                    }
                }

                // Game Details (Name, Status Badge, Path)
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 6

                    RowLayout {
                        spacing: 10

                        Text {
                            text: root.getGameName(appBackend ? appBackend.gamePath : "")
                            font.pixelSize: 16
                            font.bold: true
                            color: Theme.textPrimary
                            elide: Text.ElideRight
                            Layout.maximumWidth: 400
                        }

                        Rectangle {
                            implicitWidth: badgeLoadedContent.implicitWidth + 14
                            implicitHeight: Theme.heightBadge
                            radius: Theme.radiusBadge
                            color: Theme.statusSuccessSubtle
                            border.color: Theme.statusSuccessBorder
                            border.width: 1

                            RowLayout {
                                id: badgeLoadedContent
                                anchors.centerIn: parent
                                spacing: 4

                                Icon {
                                    glyph: Icons.circleCheck
                                    size: 11
                                    color: Theme.statusSuccess
                                }
                                Text {
                                    text: root.t("dashboard.game_loaded_badge")
                                    font.pixelSize: 11
                                    font.bold: true
                                    color: Theme.statusSuccess
                                }
                            }
                        }
                    }

                    RowLayout {
                        spacing: 6
                        Layout.fillWidth: true

                        Icon {
                            glyph: Icons.folder
                            size: 12
                            color: Theme.textSecondary
                        }

                        Text {
                            Layout.fillWidth: true
                            text: appBackend ? appBackend.gamePath : ""
                            font.pixelSize: 12
                            color: Theme.textSecondary
                            elide: Text.ElideMiddle
                        }
                    }
                }

                // Action Buttons
                RowLayout {
                    spacing: 8

                    // Klasörü Aç
                    Button {
                        id: btnOpenFolder
                        implicitHeight: Theme.heightSecondary
                        topInset: 0; bottomInset: 0; leftInset: 0; rightInset: 0; padding: 0
                        scale: down ? 0.98 : 1.0

                        background: Rectangle {
                            radius: Theme.radiusControl
                            color: btnOpenFolder.down ? Theme.surfaceHover : (btnOpenFolder.hovered ? Theme.surfaceHover : Theme.surfaceControl)
                            border.color: btnOpenFolder.hovered ? Theme.borderFocus : Theme.borderControl
                            border.width: 1
                            Behavior on color { ColorAnimation { duration: 120 } }
                            Behavior on border.color { ColorAnimation { duration: 120 } }
                        }

                        contentItem: RowLayout {
                            spacing: 6
                            anchors.centerIn: parent
                            anchors.leftMargin: 12
                            anchors.rightMargin: 12
                            Icon {
                                glyph: Icons.folderOpen
                                size: 13
                                color: btnOpenFolder.hovered ? Theme.textPrimary : Theme.textSecondary
                            }
                            Text {
                                text: root.t("dashboard.open_game_folder_btn")
                                font.pixelSize: 12
                                color: btnOpenFolder.hovered ? Theme.textPrimary : Theme.textSecondary
                            }
                        }

                        onClicked: {
                            if (appBackend) appBackend.openGameFolder();
                        }
                    }

                    // Farklı Oyun Seç...
                    Button {
                        id: btnChangeGame
                        implicitHeight: Theme.heightSecondary
                        topInset: 0; bottomInset: 0; leftInset: 0; rightInset: 0; padding: 0
                        scale: down ? 0.98 : 1.0

                        background: Rectangle {
                            radius: Theme.radiusControl
                            color: btnChangeGame.down ? Theme.accentSolid : (btnChangeGame.hovered ? Theme.accentHover : Theme.accentSolid)
                            border.width: 0
                            Behavior on color { ColorAnimation { duration: 120 } }
                        }

                        contentItem: RowLayout {
                            spacing: 6
                            anchors.centerIn: parent
                            anchors.leftMargin: 14
                            anchors.rightMargin: 14
                            Icon {
                                glyph: Icons.refreshCw
                                size: 13
                                color: Theme.accentContrastText
                            }
                            Text {
                                text: root.t("dashboard.change_game_btn")
                                font.pixelSize: 12
                                font.bold: true
                                color: Theme.accentContrastText
                            }
                        }

                        onClicked: folderDialog.open()
                    }
                }
            }
        }

        // 3. Engine Diagnostics Card
        Rectangle {
            width: parent.width
            implicitHeight: diagContent.implicitHeight + 36
            radius: Theme.radiusCard
            color: clrCard
            border.color: clrCardBorder
            border.width: 1

            Column {
                id: diagContent
                anchors.top: parent.top
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.margins: 18
                spacing: 16

                RowLayout {
                    width: parent.width
                    spacing: 8
                    Icon {
                        glyph: Icons.stethoscope
                        size: 16
                        color: Theme.accentSolid
                    }
                    Text {
                        text: root.t("dashboard.profiler_title")
                        font.pixelSize: 15
                        font.bold: true
                        color: Theme.textPrimary
                    }
                    Item { Layout.fillWidth: true }
                    Rectangle {
                        implicitWidth: routeLabel.implicitWidth + 16
                        implicitHeight: Theme.heightBadge
                        radius: Theme.radiusBadge
                        color: Theme.accentSubtle
                        border.color: Theme.accentBorder
                        border.width: 1
                        Text {
                            id: routeLabel
                            anchors.centerIn: parent
                            text: appBackend ? appBackend.recommendedRoute : root.t("dashboard.select_game_first")
                            font.pixelSize: 11
                            font.bold: true
                            color: Theme.isDark ? Theme.accentHover : Theme.accentSolid
                        }
                    }
                }

                // 4 Metric Badges
                Flow {
                    width: parent.width
                    spacing: 12

                    // Badge 1: Unity Version
                    Rectangle {
                        width: (parent.width - 36) / 4
                        height: 70
                        radius: Theme.radiusControl
                        color: Theme.surfaceControl
                        border.color: clrCardBorder
                        Column {
                            anchors.centerIn: parent
                            spacing: 4
                            Text { 
                                text: root.t("dashboard.unity_version")
                                font.pixelSize: 11
                                color: clrTxt2 
                            }
                            Text { 
                                text: appBackend ? appBackend.unityVersion : ""
                                font.pixelSize: 14
                                font.bold: true
                                color: clrTxt 
                            }
                        }
                    }

                    // Badge 2: Architecture
                    Rectangle {
                        width: (parent.width - 36) / 4
                        height: 70
                        radius: Theme.radiusControl
                        color: Theme.surfaceControl
                        border.color: clrCardBorder
                        Column {
                            anchors.centerIn: parent
                            spacing: 4
                            Text { 
                                text: root.t("dashboard.architecture")
                                font.pixelSize: 11
                                color: clrTxt2 
                            }
                            Text { 
                                text: appBackend ? appBackend.architecture : ""
                                font.pixelSize: 14
                                font.bold: true
                                color: clrAccentCyan 
                            }
                        }
                    }

                    // Badge 3: TextMeshPro
                    Rectangle {
                        width: (parent.width - 36) / 4
                        height: 70
                        radius: Theme.radiusControl
                        color: Theme.surfaceControl
                        border.color: clrCardBorder
                        Column {
                            anchors.centerIn: parent
                            spacing: 4
                            Text { 
                                text: root.t("dashboard.text_engine")
                                font.pixelSize: 11
                                color: clrTxt2 
                            }
                            Text {
                                text: (appBackend && appBackend.hasTextMeshPro)
                                      ? root.t("dashboard.tmp_detected")
                                      : root.t("dashboard.ugui_detected")
                                font.pixelSize: 13
                                font.bold: true
                                color: (appBackend && appBackend.hasTextMeshPro) ? Theme.statusSuccess : clrTxt2
                            }
                        }
                    }

                    // Badge 4: BepInEx Mod Status
                    Rectangle {
                        width: (parent.width - 36) / 4
                        height: 70
                        radius: Theme.radiusControl
                        color: Theme.surfaceControl
                        border.color: clrCardBorder
                        Column {
                            anchors.centerIn: parent
                            spacing: 4
                            Text { 
                                text: root.t("dashboard.hook_status")
                                font.pixelSize: 11
                                color: clrTxt2 
                            }
                            Text {
                                text: (appBackend && appBackend.hasBepInEx) 
                                      ? root.t("dashboard.bepinex_active")
                                      : root.t("dashboard.vanilla")
                                font.pixelSize: 13
                                font.bold: true
                                color: (appBackend && appBackend.hasBepInEx) ? Theme.statusSuccess : Theme.statusWarning
                            }
                        }
                    }
                }
            }
        }

        // 4. Quick Settings Card (per-run choices; detailed options live in Settings)
        Rectangle {
            width: parent.width
            implicitHeight: quickCol.implicitHeight + 36
            radius: Theme.radiusCard
            color: clrCard
            border.color: clrCardBorder
            border.width: 1

            ColumnLayout {
                id: quickCol
                anchors.top: parent.top
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.margins: 18
                spacing: 12

                // Header styled like the diagnostics card: title + pill badge
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    Icon {
                        glyph: Icons.slidersHorizontal
                        size: 16
                        color: Theme.accentSolid
                    }
                    Text {
                        text: root.t("dashboard.quick_settings_title")
                        font.pixelSize: 15
                        font.bold: true
                        color: Theme.textPrimary
                    }
                    Item { Layout.fillWidth: true }
                    Rectangle {
                        implicitWidth: langCountRow.implicitWidth + 16
                        implicitHeight: Theme.heightBadge
                        radius: Theme.radiusBadge
                        color: Theme.accentSubtle
                        border.color: Theme.accentBorder
                        border.width: 1
                        RowLayout {
                            id: langCountRow
                            anchors.centerIn: parent
                            spacing: 4
                            Icon {
                                glyph: Icons.globe
                                size: 12
                                color: Theme.isDark ? Theme.accentHover : Theme.accentSolid
                            }
                            Text {
                                text: root.t("dashboard.quick_lang_count")
                                        .replace("{count}", appBackend ? appBackend.supportedTargetLanguages.length : 0)
                                font.pixelSize: 11
                                font.bold: true
                                color: Theme.isDark ? Theme.accentHover : Theme.accentSolid
                            }
                        }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 12

                    NeonSelect {
                        Layout.fillWidth: true
                        Layout.preferredWidth: 1
                        iconGlyph: Icons.languages
                        caption: root.t("dashboard.quick_source")
                        enabled: Boolean(appBackend && !appBackend.isBusy)
                        searchable: true
                        searchPlaceholder: root.t("dashboard.lang_search_placeholder")
                        emptyText: root.t("dashboard.lang_search_empty")
                        warning: Boolean(appBackend && !appBackend.languagesSupportedByEngine && appBackend.sourceLanguage !== "auto")
                        model: {
                            var autoName = root.t("settings.source_language_auto");
                            var langs = appBackend ? appBackend.supportedTargetLanguages : [];
                            return [{ code: "auto", name: autoName }].concat(langs);
                        }
                        currentValue: appBackend ? appBackend.sourceLanguage : "auto"
                        onActivated: (value) => { if (appBackend) appBackend.setSourceLanguage(value); }
                    }

                    Text {
                        text: "→"
                        font.pixelSize: 18
                        font.bold: true
                        color: clrAccentCyan
                    }

                    NeonSelect {
                        Layout.fillWidth: true
                        Layout.preferredWidth: 1
                        iconGlyph: Icons.target
                        caption: root.t("dashboard.quick_target")
                        enabled: Boolean(appBackend && !appBackend.isBusy)
                        searchable: true
                        searchPlaceholder: root.t("dashboard.lang_search_placeholder")
                        emptyText: root.t("dashboard.lang_search_empty")
                        warning: Boolean(appBackend && !appBackend.languagesSupportedByEngine)
                        model: appBackend ? appBackend.supportedTargetLanguages : []
                        currentValue: appBackend ? appBackend.targetLanguage : ""
                        onActivated: (value) => { if (appBackend) appBackend.setTargetLanguage(value); }
                    }

                    NeonSelect {
                        Layout.fillWidth: true
                        Layout.preferredWidth: 1
                        iconGlyph: Icons.bot
                        caption: root.t("dashboard.quick_engine")
                        enabled: Boolean(appBackend && !appBackend.isBusy)
                        valueRole: "id"
                        model: appBackend ? appBackend.supportedEngines : []
                        currentValue: appBackend ? appBackend.selectedEngine : ""
                        onActivated: (value) => { if (appBackend) appBackend.setSelectedEngine(value); }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    visible: Boolean(appBackend && !appBackend.languagesSupportedByEngine)
                    spacing: 6
                    Icon { glyph: Icons.triangleAlert; size: 14; color: "#F59E0B"; Layout.alignment: Qt.AlignTop }
                    Text {
                        Layout.fillWidth: true
                        wrapMode: Text.WordWrap
                        text: root.t("dashboard.quick_lang_unsupported")
                        font.pixelSize: 11
                        color: "#F59E0B"
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    visible: Boolean(appBackend && appBackend.targetIsRtl)
                    spacing: 6
                    readonly property bool shaped: Boolean(appBackend && appBackend.rtlStaticShaping)
                    Icon {
                        glyph: parent.shaped ? Icons.languages : Icons.triangleAlert
                        size: 14
                        color: parent.shaped ? clrAccentCyan : "#F59E0B"
                        Layout.alignment: Qt.AlignTop
                    }
                    Text {
                        Layout.fillWidth: true
                        wrapMode: Text.WordWrap
                        text: parent.shaped ? root.t("dashboard.quick_rtl_on") : root.t("dashboard.quick_rtl_off")
                        font.pixelSize: 11
                        color: parent.shaped ? clrAccentCyan : "#F59E0B"
                    }
                }
            }
        }

        // Notices: warnings and results that must not hide in the console log
        Column {
            id: noticesColumn
            width: parent.width
            spacing: 8
            visible: Boolean(appBackend && appBackend.notices.length > 0)

            RowLayout {
                width: parent.width
                Text {
                    text: root.t("dashboard.notices_title")
                    font.pixelSize: 13
                    font.bold: true
                    color: Theme.textPrimary
                }
                Item { Layout.fillWidth: true }
                Button {
                    id: btnDismissNotices
                    flat: true
                    implicitHeight: 24
                    topInset: 0; bottomInset: 0; padding: 4
                    contentItem: Text {
                        text: root.t("dashboard.notices_dismiss")
                        font.pixelSize: 12
                        color: btnDismissNotices.hovered ? Theme.textPrimary : Theme.textSecondary
                    }
                    background: Item {}
                    onClicked: {
                        if (appBackend) appBackend.dismissNotices();
                    }
                }
            }

            Repeater {
                model: appBackend ? appBackend.notices : []
                delegate: Rectangle {
                    width: noticesColumn.width
                    implicitHeight: noticeText.implicitHeight + 20
                    radius: Theme.radiusControl
                    color: modelData.level === "error" ? Theme.statusDangerSubtle
                         : modelData.level === "success" ? Theme.statusSuccessSubtle
                         : modelData.level === "info" ? Theme.surfaceControl
                         : Theme.statusWarningSubtle
                    border.width: 1
                    border.color: modelData.level === "error" ? Theme.statusDangerBorder
                                : modelData.level === "success" ? Theme.statusSuccessBorder
                                : modelData.level === "info" ? Theme.borderControl
                                : Theme.statusWarningBorder

                    Text {
                        id: noticeText
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.margins: 14
                        text: modelData.text
                        font.pixelSize: 12
                        wrapMode: Text.WordWrap
                        color: modelData.level === "error" ? Theme.statusDanger
                             : modelData.level === "success" ? Theme.statusSuccess
                             : modelData.level === "info" ? Theme.textSecondary
                             : Theme.statusWarning
                    }
                }
            }
        }

        // 5. Action & Progress Card
        Rectangle {
            width: parent.width
            implicitHeight: actionContent.implicitHeight + 36
            radius: Theme.radiusCard
            color: clrCard
            border.color: clrCardBorder
            border.width: 1

            Column {
                id: actionContent
                anchors.top: parent.top
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.margins: 18
                spacing: 16

                RowLayout {
                    width: parent.width
                    spacing: 8
                    Icon {
                        glyph: Icons.zap
                        size: 16
                        color: Theme.accentSolid
                    }
                    Text {
                        text: root.t("dashboard.pipeline_title")
                        font.pixelSize: 15
                        font.bold: true
                        color: Theme.textPrimary
                    }
                    Item { Layout.fillWidth: true }
                    Text {
                        text: appBackend ? appBackend.statusText : ""
                        font.pixelSize: 12
                        color: (appBackend && appBackend.isBusy) ? clrAccentCyan : clrTxt2
                    }
                }

                Text {
                    width: parent.width
                    text: root.t("dashboard.pipeline_desc")
                    font.pixelSize: 12
                    color: Theme.textSecondary
                    wrapMode: Text.WordWrap
                    visible: !Boolean(appBackend && appBackend.isBusy)
                }

                Column {
                    width: parent.width
                    spacing: 6
                    visible: Boolean(appBackend && appBackend.isBusy)

                    ProgressBar {
                        width: parent.width
                        value: appBackend ? appBackend.progress : 0
                        indeterminate: Boolean(appBackend && appBackend.progress <= 0)
                    }

                    Text {
                        width: parent.width
                        text: appBackend ? appBackend.progressMessage : ""
                        font.pixelSize: 12
                        color: clrTxt2
                        elide: Text.ElideRight
                    }
                }

                // Big Glowing Action Button + Stop
                RowLayout {
                    width: parent.width
                    spacing: 12

                Button {
                    Layout.fillWidth: true
                    Layout.preferredHeight: Theme.heightPrimaryCTA
                    topInset: 0; bottomInset: 0; leftInset: 0; rightInset: 0; padding: 0
                    enabled: Boolean(appBackend && appBackend.gamePath && !appBackend.isBusy)
                    scale: down ? 0.98 : (hovered ? 1.01 : 1.0)
                    Behavior on scale { NumberAnimation { duration: 120 } }
                    onClicked: {
                        if (appBackend) appBackend.startLocalization();
                    }

                    background: Rectangle {
                        radius: Theme.radiusControl
                        color: {
                            if (!parent.enabled) return Theme.isDark ? "#232A3B" : "#CBD5E1";
                            if (Theme.isNeon) {
                                return parent.down ? Theme.accentAlpha(0.45) : (parent.hovered ? Theme.accentAlpha(0.35) : Theme.accentAlpha(0.25));
                            }
                            return parent.down ? Theme.accentSolid : (parent.hovered ? Theme.accentHover : Theme.accentSolid);
                        }
                        border.color: {
                            if (!parent.enabled) return "transparent";
                            if (Theme.isNeon) return parent.hovered ? Theme.accentHover : Theme.accentAlpha(0.8);
                            return "transparent";
                        }
                        border.width: Theme.isNeon ? 1.5 : 0
                        opacity: parent.enabled ? 1.0 : 0.5
                        Behavior on color { ColorAnimation { duration: 120 } }
                    }

                    contentItem: RowLayout {
                        spacing: 10
                        anchors.centerIn: parent
                        Icon {
                            glyph: (appBackend && appBackend.isBusy) ? Icons.refreshCw : Icons.rocket
                            size: 18
                            color: {
                                if (!parent.parent.enabled) return Theme.textMuted;
                                if (Theme.isNeon) return Theme.textPrimary;
                                return Theme.accentContrastText;
                            }
                        }
                        Text {
                            text: (appBackend && appBackend.isBusy)
                                  ? root.t("dashboard.translating_status")
                                  : root.t("dashboard.start_translation_btn")
                            font.pixelSize: 15
                            font.bold: true
                            font.letterSpacing: 0.5
                            color: {
                                if (!parent.parent.enabled) return Theme.textMuted;
                                if (Theme.isNeon) return Theme.textPrimary;
                                return Theme.accentContrastText;
                            }
                        }
                    }
                }

                Button {
                    Layout.preferredWidth: 150
                    Layout.preferredHeight: Theme.heightPrimaryCTA
                    topInset: 0; bottomInset: 0; leftInset: 0; rightInset: 0; padding: 0
                    visible: Boolean(appBackend && appBackend.isBusy)
                    scale: down ? 0.97 : (hovered ? 1.02 : 1.0)
                    Behavior on scale { NumberAnimation { duration: 120 } }
                    onClicked: {
                        if (appBackend) appBackend.stopTranslation();
                    }
                    background: Rectangle {
                        radius: Theme.radiusControl
                        color: parent.hovered ? Qt.rgba(244/255, 63/255, 94/255, 0.22) : Qt.rgba(244/255, 63/255, 94/255, 0.12)
                        border.color: Theme.statusDanger
                        border.width: 1
                    }
                    contentItem: RowLayout {
                        spacing: 8
                        anchors.centerIn: parent
                        Icon { glyph: Icons.square; size: 14; color: Theme.statusDanger }
                        Text {
                            text: root.t("dashboard.stop_btn")
                            font.pixelSize: 14
                            font.bold: true
                            color: Theme.statusDanger
                        }
                    }
                }
                }

                // Review shortcut once a run produced results
                Button {
                    width: parent.width
                    height: 44
                    topInset: 0; bottomInset: 0; leftInset: 0; rightInset: 0; padding: 0
                    visible: Boolean(editorBackend && editorBackend.hasSession && appBackend && !appBackend.isBusy)
                    onClicked: root.openEditorRequested()
                    background: Rectangle {
                        radius: Theme.radiusControl
                        color: parent.hovered ? Theme.accentSubtle : Theme.surfaceControl
                        border.color: Theme.borderFocus
                        border.width: 1
                    }
                    contentItem: RowLayout {
                        spacing: 8
                        anchors.centerIn: parent
                        Icon { glyph: Icons.squarePen; size: 16; color: Theme.isDark ? Theme.accentHover : Theme.accentSolid }
                        Text {
                            text: {
                                if (!editorBackend || !localeManager) return "";
                                var c = editorBackend.counts;
                                var problems = (c["rejected"] || 0) + (c["failed"] || 0) + (c["invalid"] || 0);
                                var key = problems > 0 ? "dashboard.review_btn_problems" : "dashboard.review_btn";
                                return root.t(key).replace("{count}", problems);
                            }
                            font.pixelSize: 13
                            font.bold: true
                            color: Theme.isDark ? Theme.accentHover : Theme.accentSolid
                        }
                    }
                }

                    // Standalone Patch Exporter & Folder Row
                    RowLayout {
                        width: parent.width
                        spacing: 12

                        Button {
                            Layout.fillWidth: true
                            height: Theme.heightSecondary
                            topInset: 0; bottomInset: 0; leftInset: 0; rightInset: 0; padding: 0
                            enabled: Boolean(appBackend && appBackend.gamePath && !appBackend.isBusy)
                            scale: down ? 0.98 : (hovered ? 1.01 : 1.0)
                            Behavior on scale { NumberAnimation { duration: 120 } }
                            onClicked: {
                                if (appBackend) appBackend.exportPatchPackage();
                            }
                            background: Rectangle {
                                radius: Theme.radiusControl
                                color: parent.hovered ? Theme.surfaceHover : Theme.surfaceControl
                                border.color: parent.hovered ? Theme.borderFocus : Theme.borderControl
                                border.width: 1
                            }
                            contentItem: RowLayout {
                                spacing: 8
                                anchors.centerIn: parent
                                Icon { glyph: Icons.packageBox; size: 15; color: parent.parent.enabled ? (parent.parent.hovered ? Theme.textPrimary : Theme.accentSolid) : Theme.textMuted }
                                Text {
                                    text: root.t("dashboard.export_patch_btn")
                                    font.pixelSize: 13
                                    font.bold: true
                                    color: parent.parent.enabled ? (parent.parent.hovered ? Theme.textPrimary : Theme.accentSolid) : Theme.textMuted
                                }
                            }
                        }

                        Button {
                            height: Theme.heightSecondary
                            Layout.preferredWidth: 160
                            topInset: 0; bottomInset: 0; leftInset: 0; rightInset: 0; padding: 0
                            scale: down ? 0.98 : (hovered ? 1.01 : 1.0)
                            Behavior on scale { NumberAnimation { duration: 120 } }
                            onClicked: {
                                if (appBackend) appBackend.openPatchFolder();
                            }
                            background: Rectangle {
                                radius: Theme.radiusControl
                                color: parent.hovered ? Theme.surfaceHover : Theme.surfaceControl
                                border.color: parent.hovered ? Theme.borderFocus : Theme.borderControl
                                border.width: 1
                            }
                            contentItem: RowLayout {
                                spacing: 6
                                anchors.centerIn: parent
                                Icon { glyph: Icons.folderOpen; size: 15; color: parent.parent.hovered ? Theme.textPrimary : Theme.textSecondary }
                                Text {
                                    text: root.t("dashboard.open_patch_folder")
                                    font.pixelSize: 12
                                    color: parent.parent.hovered ? Theme.textPrimary : Theme.textSecondary
                                }
                            }
                        }
                    }
                }
            }
        }

    CompletionDialog {
        id: completionDialog
        onOpenEditorRequested: root.openEditorRequested()
    }

    Connections {
        target: appBackend
        ignoreUnknownSignals: true
        function onPipelineCompleted(summary) {
            var data = (summary !== undefined && summary !== null) ? summary : (arguments.length > 0 ? arguments[0] : {});
            completionDialog.openWithSummary(data);
        }
    }

    FolderDialog {
        id: folderDialog
        title: root.t("dashboard.folder_dialog_title")
        onAccepted: {
            if (appBackend) appBackend.selectGame(selectedFolder);
        }
    }
}
