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

    // Palette references
    readonly property color clrCard:       "#151A29"
    readonly property color clrCardHover:  "#1D2436"
    readonly property color clrCardBorder: "#242C44"
    readonly property color clrAccent:     "#8B5CF6"
    readonly property color clrAccentCyan: "#00F2FE"
    readonly property color clrTxt:        "#F3F4F6"
    readonly property color clrTxt2:       "#9CA3AF"

    function t(key) {
        return (localeManager && localeManager.currentLanguage, localeManager ? localeManager.t(key) : "");
    }

    Column {
        width: Math.min(parent.width - 48, 920)
        anchors.horizontalCenter: parent.horizontalCenter
        spacing: 20
        topPadding: 24
        bottomPadding: 40

        // 1. Header
        Column {
            spacing: 6
            Text {
                text: root.t("dashboard.title")
                font.pixelSize: 26
                font.bold: true
                color: clrTxt
            }
            Text {
                text: root.t("dashboard.subtitle")
                font.pixelSize: 13
                color: clrTxt2
            }
        }

        // 2. Game Selection Drop Zone Card
        Rectangle {
            id: dropCard
            width: parent.width
            implicitHeight: dropContent.implicitHeight + 40
            radius: 14
            color: dragArea.containsDrag ? "#212842" : (dropMouseArea.containsMouse ? clrCardHover : clrCard)
            border.color: dragArea.containsDrag ? clrAccentCyan : (dropMouseArea.containsMouse ? Qt.rgba(139/255, 92/255, 246/255, 0.5) : clrCardBorder)
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
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: folderDialog.open()
            }

            Column {
                id: dropContent
                anchors.top: parent.top
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.topMargin: 20
                spacing: 12

                Text {
                    text: (appBackend && appBackend.gamePath) ? "🎮" : "📁"
                    font.pixelSize: 32
                    anchors.horizontalCenter: parent.horizontalCenter
                }

                Text {
                    text: (appBackend && appBackend.gamePath)
                          ? appBackend.gamePath 
                          : root.t("dashboard.drag_drop_hint")
                    font.pixelSize: 14
                    font.bold: Boolean(appBackend && appBackend.gamePath)
                    color: (appBackend && appBackend.gamePath) ? clrAccentCyan : clrTxt2
                    anchors.horizontalCenter: parent.horizontalCenter
                    elide: Text.ElideMiddle
                    width: parent.width - 40
                    horizontalAlignment: Text.AlignHCenter
                }

                Button {
                    text: (appBackend && appBackend.gamePath) 
                          ? root.t("dashboard.change_game_btn")
                          : root.t("dashboard.select_game_btn")
                    anchors.horizontalCenter: parent.horizontalCenter
                    Material.background: clrAccent
                    scale: down ? 0.96 : (hovered ? 1.03 : 1.0)
                    Behavior on scale { NumberAnimation { duration: 120 } }
                    onClicked: folderDialog.open()
                }
            }
        }

        // 3. Engine Diagnostics Card
        Rectangle {
            width: parent.width
            implicitHeight: diagContent.implicitHeight + 36
            radius: 14
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
                    Text {
                        text: "🩺 " + root.t("dashboard.profiler_title")
                        font.pixelSize: 16
                        font.bold: true
                        color: clrTxt
                    }
                    Item { Layout.fillWidth: true }
                    Rectangle {
                        implicitWidth: routeLabel.implicitWidth + 16
                        implicitHeight: 24
                        radius: 12
                        color: Qt.rgba(0, 242/255, 254/255, 0.12)
                        border.color: Qt.rgba(0, 242/255, 254/255, 0.4)
                        Text {
                            id: routeLabel
                            anchors.centerIn: parent
                            text: appBackend ? appBackend.recommendedRoute : root.t("dashboard.select_game_first")
                            font.pixelSize: 11
                            font.bold: true
                            color: clrAccentCyan
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
                        radius: 10
                        color: "#1A2033"
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
                        radius: 10
                        color: "#1A2033"
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
                        radius: 10
                        color: "#1A2033"
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
                                color: (appBackend && appBackend.hasTextMeshPro) ? "#10B981" : clrTxt2
                            }
                        }
                    }

                    // Badge 4: BepInEx Mod Status
                    Rectangle {
                        width: (parent.width - 36) / 4
                        height: 70
                        radius: 10
                        color: "#1A2033"
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
                                color: (appBackend && appBackend.hasBepInEx) ? "#10B981" : "#F59E0B"
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
            radius: 14
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
                    Text {
                        text: "🎛️ " + root.t("dashboard.quick_settings_title")
                        font.pixelSize: 16
                        font.bold: true
                        color: clrTxt
                    }
                    Item { Layout.fillWidth: true }
                    Rectangle {
                        implicitWidth: langCountLabel.implicitWidth + 16
                        implicitHeight: 24
                        radius: 12
                        color: Qt.rgba(0, 0.95, 1, 0.12)
                        border.color: Qt.rgba(0, 0.95, 1, 0.4)
                        Text {
                            id: langCountLabel
                            anchors.centerIn: parent
                            text: "🌍 " + root.t("dashboard.quick_lang_count")
                                    .replace("{count}", appBackend ? appBackend.supportedTargetLanguages.length : 0)
                            font.pixelSize: 11
                            font.bold: true
                            color: clrAccentCyan
                        }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 12

                    NeonSelect {
                        Layout.fillWidth: true
                        Layout.preferredWidth: 1
                        icon: "🗣️"
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
                        icon: "🎯"
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
                        icon: "🤖"
                        caption: root.t("dashboard.quick_engine")
                        enabled: Boolean(appBackend && !appBackend.isBusy)
                        valueRole: "id"
                        model: appBackend ? appBackend.supportedEngines : []
                        currentValue: appBackend ? appBackend.selectedEngine : ""
                        onActivated: (value) => { if (appBackend) appBackend.setSelectedEngine(value); }
                    }
                }

                Text {
                    Layout.fillWidth: true
                    visible: Boolean(appBackend && !appBackend.languagesSupportedByEngine)
                    wrapMode: Text.WordWrap
                    text: root.t("dashboard.quick_lang_unsupported")
                    font.pixelSize: 11
                    color: "#F59E0B"
                }

                Text {
                    Layout.fillWidth: true
                    visible: Boolean(appBackend && appBackend.targetIsRtl)
                    wrapMode: Text.WordWrap
                    text: (appBackend && appBackend.rtlStaticShaping)
                          ? root.t("dashboard.quick_rtl_on")
                          : root.t("dashboard.quick_rtl_off")
                    font.pixelSize: 11
                    color: (appBackend && appBackend.rtlStaticShaping) ? clrAccentCyan : "#F59E0B"
                }
            }
        }

        // 5. Action & Progress Card
        Rectangle {
            width: parent.width
            implicitHeight: actionContent.implicitHeight + 36
            radius: 14
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
                    Text {
                        text: "⚡ " + root.t("dashboard.pipeline_title")
                        font.pixelSize: 16
                        font.bold: true
                        color: clrTxt
                    }
                    Item { Layout.fillWidth: true }
                    Text {
                        text: appBackend ? appBackend.statusText : ""
                        font.pixelSize: 12
                        color: (appBackend && appBackend.isBusy) ? clrAccentCyan : clrTxt2
                    }
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

                // Quick Hook Install Prompt if game selected but has no BepInEx
                Rectangle {
                    width: parent.width
                    height: 44
                    radius: 8
                    color: Qt.rgba(245/255, 158/255, 11/255, 0.12)
                    border.color: Qt.rgba(245/255, 158/255, 11/255, 0.4)
                    border.width: 1
                    visible: Boolean(appBackend && appBackend.gamePath && !appBackend.hasBepInEx && !appBackend.isBusy)

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 14
                        anchors.rightMargin: 12
                        spacing: 10

                        Text {
                            text: "⚠️"
                            font.pixelSize: 16
                        }

                        Text {
                            Layout.fillWidth: true
                            text: root.t("dashboard.quick_install_hint")
                            font.pixelSize: 12
                            color: "#FCD34D"
                            elide: Text.ElideRight
                        }

                        Button {
                            text: root.t("dashboard.quick_install_hooks")
                            Material.background: "#F59E0B"
                            scale: down ? 0.95 : (hovered ? 1.03 : 1.0)
                            Behavior on scale { NumberAnimation { duration: 120 } }
                            onClicked: {
                                if (appBackend) appBackend.installHooks();
                            }
                        }
                    }
                }

                // Big Glowing Action Button + Stop
                RowLayout {
                    width: parent.width
                    spacing: 12

                Button {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 52
                    topInset: 0
                    bottomInset: 0
                    enabled: Boolean(appBackend && appBackend.gamePath && !appBackend.isBusy)
                    scale: down ? 0.98 : (hovered ? 1.01 : 1.0)
                    Behavior on scale { NumberAnimation { duration: 120 } }
                    onClicked: {
                        if (appBackend) appBackend.startLocalization();
                    }

                    background: Rectangle {
                        radius: 10
                        gradient: Gradient {
                            orientation: Gradient.Horizontal
                            GradientStop { position: 0.0; color: "#8B5CF6" }
                            GradientStop { position: 1.0; color: "#00F2FE" }
                        }
                        opacity: parent.enabled ? 1.0 : 0.4
                    }

                    contentItem: Row {
                        anchors.centerIn: parent
                        spacing: 10
                        Text { text: (appBackend && appBackend.isBusy) ? "⏳" : "🚀"; font.pixelSize: 20 }
                        Text {
                            text: (appBackend && appBackend.isBusy)
                                  ? root.t("dashboard.translating_status")
                                  : root.t("dashboard.start_translation_btn")
                            font.pixelSize: 15
                            font.bold: true
                            color: "#FFFFFF"
                        }
                    }
                }

                Button {
                    Layout.preferredWidth: 150
                    Layout.preferredHeight: 52
                    topInset: 0
                    bottomInset: 0
                    visible: Boolean(appBackend && appBackend.isBusy)
                    scale: down ? 0.97 : (hovered ? 1.02 : 1.0)
                    Behavior on scale { NumberAnimation { duration: 120 } }
                    onClicked: {
                        if (appBackend) appBackend.stopTranslation();
                    }
                    background: Rectangle {
                        radius: 10
                        color: parent.hovered ? "#4A1414" : "#2A1010"
                        border.color: "#EF4444"
                        border.width: 1
                    }
                    contentItem: Text {
                        text: "⏹ " + root.t("dashboard.stop_btn")
                        font.pixelSize: 14
                        font.bold: true
                        color: "#EF4444"
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                }
                }

                // Review shortcut once a run produced results
                Button {
                    width: parent.width
                    height: 44
                    visible: Boolean(editorBackend && editorBackend.hasSession && appBackend && !appBackend.isBusy)
                    onClicked: root.openEditorRequested()
                    background: Rectangle {
                        radius: 10
                        color: parent.hovered ? "#1D2436" : "#121827"
                        border.color: "#00F2FE"
                        border.width: 1
                    }
                    contentItem: Text {
                        text: {
                            if (!editorBackend || !localeManager) return "";
                            var c = editorBackend.counts;
                            var problems = (c["rejected"] || 0) + (c["failed"] || 0) + (c["invalid"] || 0);
                            var key = problems > 0 ? "dashboard.review_btn_problems" : "dashboard.review_btn";
                            return "📝 " + root.t(key).replace("{count}", problems);
                        }
                        font.pixelSize: 13
                        font.bold: true
                        color: "#00F2FE"
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                }

                    // Standalone Patch Exporter & Folder Row
                    RowLayout {
                        width: parent.width
                        spacing: 12

                        Button {
                            Layout.fillWidth: true
                            height: 44
                            enabled: Boolean(appBackend && appBackend.gamePath && !appBackend.isBusy)
                            Material.background: "#1E293B"
                            scale: down ? 0.98 : (hovered ? 1.01 : 1.0)
                            Behavior on scale { NumberAnimation { duration: 120 } }
                            onClicked: {
                                if (appBackend) appBackend.exportPatchPackage();
                            }

                            contentItem: Row {
                                anchors.centerIn: parent
                                spacing: 8
                                Text {
                                    text: root.t("dashboard.export_patch_btn")
                                    font.pixelSize: 13
                                    font.bold: true
                                    color: "#38BDF8"
                                }
                            }
                        }

                        Button {
                            height: 44
                            Layout.preferredWidth: 160
                            Material.background: "#1E293B"
                            scale: down ? 0.98 : (hovered ? 1.01 : 1.0)
                            Behavior on scale { NumberAnimation { duration: 120 } }
                            onClicked: {
                                if (appBackend) appBackend.openPatchFolder();
                            }

                            contentItem: Row {
                                anchors.centerIn: parent
                                spacing: 6
                                Text { text: "📂"; font.pixelSize: 15 }
                                Text {
                                    text: root.t("dashboard.open_patch_folder")
                                    font.pixelSize: 12
                                    color: clrTxt
                                }
                            }
                        }
                    }
                }
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
