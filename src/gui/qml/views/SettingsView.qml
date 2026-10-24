import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import QtQuick.Layouts
import QtQuick.Dialogs
import "../components"

// Every control saves immediately through appBackend.setSetting (no Save button).
ScrollView {
    id: root
    contentWidth: availableWidth
    clip: true

    readonly property color clrCard:       Theme.surfaceCard
    readonly property color clrCardHover:  Theme.surfaceHover
    readonly property color clrCardBorder: Theme.borderCard
    readonly property color clrInput:      Theme.surfaceControl
    readonly property color clrAccent:     Theme.accentSolid
    readonly property color clrTxt:        Theme.textPrimary
    readonly property color clrTxt2:       Theme.textSecondary
    readonly property color clrTxtDim:     Theme.textMuted

    property int activeSubTab: 0

    function t(key) {
        return (localeManager && localeManager.currentLanguage, localeManager ? localeManager.t(key) : "");
    }

    function choices(keys, prefix) {
        var out = [];
        for (var i = 0; i < keys.length; i++) out.push({ code: keys[i], name: t(prefix + keys[i]) });
        return out;
    }

    Column {
        width: Math.min(parent.width - 48, 920)
        anchors.horizontalCenter: parent.horizontalCenter
        spacing: 20
        topPadding: 24
        bottomPadding: 40

        // Page header (DESIGN.md §4: 22px SemiBold textPrimary, 13px textSecondary)
        Column {
            spacing: 6
            Text {
                text: "⚙️ " + root.t("settings.title")
                font.pixelSize: 22
                font.bold: true
                color: Theme.textPrimary
            }
            Text {
                text: root.t("settings.subtitle")
                font.pixelSize: 13
                color: Theme.textSecondary
            }
        }

        // Segmented Sub-Tabs Bar (DESIGN.md §3.4: Solid cohesive container)
        Rectangle {
            width: parent.width
            implicitHeight: 46
            radius: Theme.radiusControl
            color: Theme.surfaceCard
            border.color: Theme.borderCard
            border.width: 1

            RowLayout {
                anchors.fill: parent
                anchors.margins: 4
                spacing: 4

                Repeater {
                    model: [
                        { icon: Icons.monitor, key: "settings.subtab_general" },
                        { icon: Icons.bot, key: "settings.subtab_ai" },
                        { icon: Icons.zap, key: "settings.subtab_perf" },
                        { icon: Icons.bookOpen, key: "settings.subtab_glossary" }
                    ]
                    delegate: Button {
                        id: subTabBtn
                        readonly property bool isSelected: root.activeSubTab === index
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        topInset: 0
                        bottomInset: 0
                        leftInset: 0
                        rightInset: 0
                        padding: 0
                        scale: down ? 0.98 : 1.0

                        background: Rectangle {
                            radius: Theme.radiusControl - 1
                            color: subTabBtn.isSelected
                                   ? Theme.accentSubtle
                                   : (subTabBtn.hovered ? Theme.surfaceHover : "transparent")
                            border.color: subTabBtn.isSelected
                                          ? Theme.accentBorder
                                          : "transparent"
                            border.width: subTabBtn.isSelected ? 1 : 0
                            Behavior on color { ColorAnimation { duration: 120 } }
                        }

                        contentItem: RowLayout {
                            spacing: 8
                            anchors.centerIn: parent

                            Icon {
                                glyph: modelData.icon
                                size: 16
                                color: subTabBtn.isSelected
                                       ? (Theme.isDark ? Theme.accentHover : Theme.accentSolid)
                                       : (subTabBtn.hovered ? Theme.textPrimary : Theme.textSecondary)
                            }

                            Label {
                                text: root.t(modelData.key)
                                font.pixelSize: 13
                                font.weight: subTabBtn.isSelected ? Font.DemiBold : Font.Normal
                                color: subTabBtn.isSelected
                                       ? Theme.textPrimary
                                       : (subTabBtn.hovered ? Theme.textPrimary : Theme.textSecondary)
                            }
                        }

                        onClicked: root.activeSubTab = index
                    }
                }
            }
        }

        // ==========================================
        // TAB 0: GENERAL
        // ==========================================
        Column {
            width: parent.width
            spacing: 18
            visible: root.activeSubTab === 0

            SettingCard {
                iconGlyph: Icons.sparkles
                title: root.t("settings.appearance_title")
                description: root.t("settings.appearance_desc")

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 16

                    // 1. Theme Mode Selector
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 8

                        Label {
                            text: root.t("settings.theme_mode_label")
                            color: Theme.textSecondary
                            font.pixelSize: 12
                            font.bold: true
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 10

                            Repeater {
                                model: [
                                    { mode: "obsidian", label: root.t("settings.theme_mode_obsidian"), icon: Icons.sparkles },
                                    { mode: "daylight", label: root.t("settings.theme_mode_daylight"), icon: Icons.lightbulb },
                                    { mode: "cyber_neon", label: root.t("settings.theme_mode_cyber_neon"), icon: Icons.zap }
                                ]
                                delegate: Button {
                                    id: themeModeBtn
                                    readonly property bool isSelected: Theme.mode === modelData.mode
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 44
                                    topInset: 0
                                    bottomInset: 0
                                    leftInset: 0
                                    rightInset: 0
                                    padding: 0
                                    scale: down ? 0.98 : 1.0

                                    background: Rectangle {
                                        radius: Theme.radiusControl
                                        color: themeModeBtn.isSelected ? Theme.accentSubtle : (themeModeBtn.hovered ? Theme.surfaceHover : Theme.surfaceControl)
                                        border.color: themeModeBtn.isSelected ? (Theme.isNeon ? Theme.accentHover : Theme.accentSolid) : Theme.borderControl
                                        border.width: themeModeBtn.isSelected ? 1.5 : 1
                                        Behavior on color { ColorAnimation { duration: 120 } }
                                        Behavior on border.color { ColorAnimation { duration: 120 } }
                                    }

                                    contentItem: RowLayout {
                                        spacing: 8
                                        anchors.fill: parent
                                        anchors.leftMargin: 14
                                        anchors.rightMargin: 14

                                        Icon {
                                            glyph: modelData.icon
                                            size: 16
                                            color: themeModeBtn.isSelected
                                                   ? (Theme.isDark ? Theme.accentHover : Theme.accentSolid)
                                                   : (themeModeBtn.hovered ? Theme.textPrimary : Theme.textSecondary)
                                        }

                                        Label {
                                            Layout.fillWidth: true
                                            text: modelData.label
                                            font.pixelSize: 13
                                            font.weight: themeModeBtn.isSelected ? Font.DemiBold : Font.Normal
                                            color: themeModeBtn.isSelected
                                                   ? Theme.textPrimary
                                                   : (themeModeBtn.hovered ? Theme.textPrimary : Theme.textSecondary)
                                            elide: Text.ElideRight
                                        }

                                        Icon {
                                            visible: themeModeBtn.isSelected
                                            glyph: Icons.circleCheck
                                            size: 14
                                            color: Theme.isDark ? Theme.accentHover : Theme.accentSolid
                                        }
                                    }

                                    onClicked: {
                                        if (appBackend) appBackend.setSetting("theme_mode", modelData.mode);
                                    }
                                }
                            }
                        }
                    }

                    // 2. Accent Preset Selector
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 8

                        Label {
                            text: root.t("settings.accent_preset_label")
                            color: Theme.textSecondary
                            font.pixelSize: 12
                            font.bold: true
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 10

                            Repeater {
                                model: [
                                    { preset: "cyan", label: root.t("settings.accent_preset_cyan"), hex: "#06B6D4" },
                                    { preset: "emerald", label: root.t("settings.accent_preset_emerald"), hex: "#10B981" },
                                    { preset: "indigo", label: root.t("settings.accent_preset_indigo"), hex: "#6366F1" },
                                    { preset: "amber", label: root.t("settings.accent_preset_amber"), hex: "#F59E0B" }
                                ]
                                delegate: Button {
                                    id: accentBtn
                                    readonly property bool isSelected: Theme.preset === modelData.preset
                                    readonly property color accentColor: modelData.hex
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 44
                                    topInset: 0
                                    bottomInset: 0
                                    leftInset: 0
                                    rightInset: 0
                                    padding: 0
                                    scale: down ? 0.98 : 1.0

                                    background: Rectangle {
                                        radius: Theme.radiusControl
                                        color: accentBtn.isSelected
                                               ? Qt.rgba(accentBtn.accentColor.r, accentBtn.accentColor.g, accentBtn.accentColor.b, 0.18)
                                               : (accentBtn.hovered ? Theme.surfaceHover : Theme.surfaceControl)
                                        border.color: accentBtn.isSelected ? accentBtn.accentColor : Theme.borderControl
                                        border.width: accentBtn.isSelected ? 1.5 : 1
                                        Behavior on color { ColorAnimation { duration: 120 } }
                                        Behavior on border.color { ColorAnimation { duration: 120 } }
                                    }

                                    contentItem: RowLayout {
                                        spacing: 8
                                        anchors.fill: parent
                                        anchors.leftMargin: 12
                                        anchors.rightMargin: 12

                                        Rectangle {
                                            width: 14
                                            height: 14
                                            radius: 7
                                            color: modelData.hex
                                            border.color: accentBtn.isSelected ? "#FFFFFF" : Qt.rgba(1, 1, 1, 0.3)
                                            border.width: accentBtn.isSelected ? 2 : 1
                                        }

                                        Label {
                                            Layout.fillWidth: true
                                            text: modelData.label
                                            font.pixelSize: 12
                                            font.weight: accentBtn.isSelected ? Font.DemiBold : Font.Normal
                                            color: accentBtn.isSelected
                                                   ? Theme.textPrimary
                                                   : (accentBtn.hovered ? Theme.textPrimary : Theme.textSecondary)
                                            elide: Text.ElideRight
                                        }

                                        Icon {
                                            visible: accentBtn.isSelected
                                            glyph: Icons.circleCheck
                                            size: 13
                                            color: modelData.hex
                                        }
                                    }

                                    onClicked: {
                                        if (appBackend) appBackend.setSetting("accent_preset", modelData.preset);
                                    }
                                }
                            }
                        }
                    }
                }
            }

            SettingCard {
                iconGlyph: Icons.languages
                title: root.t("settings.ui_language_title")
                description: root.t("settings.ui_language_desc")
                NeonSelect {
                    Layout.preferredWidth: 340
                    icon: "🌐"
                    caption: root.t("settings.ui_language_caption")
                    model: localeManager ? localeManager.supportedLanguages : []
                    currentValue: localeManager ? localeManager.currentLanguage : ""
                    onActivated: (value) => { if (localeManager) localeManager.setLanguage(value); }
                }
            }

            SettingCard {
                iconGlyph: Icons.packageBox
                title: root.t("settings.patch_options_title")
                description: root.t("settings.patch_options_hint")
                CheckBox {
                    text: root.t("settings.rtl_shaping_checkbox")
                    checked: Boolean(appBackend && appBackend.rtlStaticShaping)
                    Material.accent: clrAccent
                    onToggled: { if (appBackend) appBackend.setRtlStaticShaping(checked); }
                }
                Label {
                    Layout.fillWidth: true
                    Layout.leftMargin: 12
                    wrapMode: Text.WordWrap
                    text: root.t("settings.rtl_shaping_desc")
                    font.pixelSize: 11
                    color: clrTxtDim
                }
                CheckBox {
                    text: root.t("settings.patch_loose_checkbox")
                    checked: Boolean(appBackend && appBackend.patchLooseFiles)
                    Material.accent: clrAccent
                    onToggled: { if (appBackend) appBackend.setPatchLooseFiles(checked); }
                }
                Label {
                    Layout.fillWidth: true
                    Layout.leftMargin: 12
                    wrapMode: Text.WordWrap
                    text: root.t("settings.patch_loose_desc")
                    font.pixelSize: 11
                    color: clrTxtDim
                }
            }

            SettingCard {
                iconGlyph: Icons.type
                title: root.t("settings.tmp_font_card_title")
                description: root.t("settings.tmp_font_card_desc")
                SettingField {
                    key: "tmp_system_font"
                    label: root.t("settings.tmp_system_font_label")
                    placeholder: "Arial"
                }
                SettingField {
                    key: "override_font_ugui"
                    label: root.t("settings.override_font_ugui_label")
                    placeholder: "Arial"
                    hint: root.t("settings.override_font_ugui_hint")
                }
            }

            SettingCard {
                iconGlyph: Icons.shieldAlert
                title: root.t("settings.backup_card_title")
                description: root.t("settings.backup_desc")
            }

            SettingCard {
                iconGlyph: Icons.sparkles
                title: root.t("settings.developer_card_title")
                SettingSwitch {
                    key: "show_debug_engines"
                    label: root.t("settings.show_debug_engines_checkbox")
                    description: root.t("settings.show_debug_engines_desc")
                }
            }
        }

        // ==========================================
        // TAB 1: ENGINES & AI
        // ==========================================
        Column {
            width: parent.width
            spacing: 18
            visible: root.activeSubTab === 1

            SettingCard {
                iconGlyph: Icons.bot
                title: root.t("settings.engine_select_title")
                description: root.t("settings.engine_select_desc")
                // Active Engine InfoBanner (DESIGN.md §3.5)
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: activeEngineRow.implicitHeight + 20
                    radius: Theme.radiusControl
                    color: Theme.surfaceSubtle
                    border.color: Theme.borderCard
                    border.width: 1

                    // Sol kenar vurgu çizgisi
                    Rectangle {
                        anchors.left: parent.left
                        anchors.top: parent.top
                        anchors.bottom: parent.bottom
                        width: 3
                        radius: 1.5
                        color: Theme.accentSolid
                    }

                    RowLayout {
                        id: activeEngineRow
                        anchors.fill: parent
                        anchors.margins: 10
                        anchors.leftMargin: 14
                        spacing: 10
                        Label { text: root.t("settings.active_engine_label"); color: clrTxt2; font.pixelSize: 12 }
                        Label {
                            Layout.fillWidth: true
                            text: {
                                var engines = appBackend ? appBackend.supportedEngines : [];
                                for (var i = 0; i < engines.length; i++) {
                                    if (engines[i].id === appBackend.selectedEngine) return engines[i].name;
                                }
                                return appBackend ? appBackend.selectedEngine : "";
                            }
                            color: Theme.isDark ? Theme.accentHover : Theme.accentSolid
                            font.pixelSize: 13
                            font.bold: true
                            elide: Text.ElideRight
                        }
                        Label { text: root.t("settings.active_engine_hint"); color: clrTxtDim; font.pixelSize: 11 }
                    }
                }
            }

            SettingCard {
                iconGlyph: Icons.sparkles
                title: root.t("settings.deepl_card_title")
                SettingField {
                    key: "deepl_key"; password: true
                    label: root.t("settings.deepl_key_label")
                    placeholder: "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx:fx"
                }
                NeonSelect {
                    Layout.preferredWidth: 340
                    caption: root.t("settings.deepl_formality_label")
                    valueRole: "code"
                    model: root.choices(["default", "more", "less"], "settings.formality_")
                    currentValue: appBackend ? appBackend.settings["deepl_formality"] : "default"
                    onActivated: (value) => appBackend.setSetting("deepl_formality", value)
                }
            }

            SettingCard {
                iconGlyph: Icons.sparkles
                title: root.t("settings.gemini_card_title")
                badge: root.t("settings.gemini_badge")
                SettingField { key: "gemini_key"; password: true; label: root.t("settings.gemini_key_label"); placeholder: "AIzaSy..." }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 14
                    SettingField { key: "gemini_model"; label: root.t("settings.gemini_model_label"); placeholder: "gemini-2.5-flash" }
                    NeonSelect {
                        Layout.preferredWidth: 300
                        caption: root.t("settings.gemini_safety_label")
                        model: root.choices(["BLOCK_NONE", "BLOCK_ONLY_HIGH", "BLOCK_MEDIUM_AND_ABOVE", "BLOCK_LOW_AND_ABOVE"], "settings.safety_")
                        currentValue: appBackend ? appBackend.settings["gemini_safety"] : "BLOCK_NONE"
                        onActivated: (value) => appBackend.setSetting("gemini_safety", value)
                    }
                }
            }

            SettingCard {
                iconGlyph: Icons.globe
                title: root.t("settings.openai_card_title")
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 14
                    SettingField { key: "openai_key"; password: true; label: root.t("settings.openai_key_label"); placeholder: "sk-..." }
                    SettingField { key: "openai_model"; label: root.t("settings.openai_model_label"); placeholder: "gpt-4o-mini" }
                }
                SettingField {
                    key: "openai_base_url"
                    label: root.t("settings.openai_base_url_label")
                    placeholder: "https://openrouter.ai/api/v1"
                    hint: root.t("settings.openai_base_url_hint")
                }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 14
                    SettingField { key: "deepseek_key"; password: true; label: root.t("settings.deepseek_key_label"); placeholder: "sk-..." }
                    SettingField { key: "deepseek_model"; label: root.t("settings.deepseek_model_label"); placeholder: "deepseek-chat" }
                }
            }

            SettingCard {
                iconGlyph: Icons.bot
                title: root.t("settings.local_llm_card_title")
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 14
                    SettingField { key: "local_llm_url"; label: root.t("settings.local_llm_url_label"); placeholder: "http://localhost:11434" }
                    SettingField { key: "local_llm_model"; label: root.t("settings.local_llm_model_label"); placeholder: "qwen2.5:latest" }
                }
                SettingSlider {
                    key: "local_llm_timeout"; label: root.t("settings.local_llm_timeout_label")
                    from: 30; to: 1800; stepSize: 30; suffix: " " + root.t("settings.unit_seconds")
                }
            }

            SettingCard {
                iconGlyph: Icons.globe
                title: root.t("settings.libre_card_title")
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 14
                    SettingField { key: "libretranslate_url"; label: root.t("settings.libre_url_label"); placeholder: "http://localhost:5000" }
                    SettingField { key: "libretranslate_key"; password: true; label: root.t("settings.libre_key_label") }
                }
            }

            SettingCard {
                iconGlyph: Icons.brain
                title: root.t("settings.ai_card_title")
                description: root.t("settings.ai_card_desc")
                SettingSlider {
                    key: "ai_temperature"; label: root.t("settings.ai_temperature_label"); hint: root.t("settings.ai_temperature_hint")
                    from: 0; to: 1; stepSize: 0.05; decimals: 2
                }
                GridLayout {
                    Layout.fillWidth: true
                    columns: 2
                    columnSpacing: 24
                    rowSpacing: 8
                    SettingSlider { key: "ai_max_tokens"; label: root.t("settings.ai_max_tokens_label"); from: 256; to: 32768; stepSize: 256 }
                    SettingSlider { key: "ai_timeout"; label: root.t("settings.ai_timeout_label"); from: 10; to: 600; stepSize: 10; suffix: " " + root.t("settings.unit_seconds") }
                    SettingSlider { key: "ai_batch_size"; label: root.t("settings.ai_batch_label"); hint: root.t("settings.ai_batch_hint"); from: 1; to: 50; stepSize: 1 }
                    SettingSlider { key: "ai_concurrency"; label: root.t("settings.ai_concurrency_label"); from: 1; to: 8; stepSize: 1 }
                    SettingSlider { key: "ai_retries"; label: root.t("settings.ai_retries_label"); from: 0; to: 5; stepSize: 1 }
                    SettingSlider { key: "ai_request_delay"; label: root.t("settings.ai_delay_label"); from: 0; to: 10; stepSize: 0.25; decimals: 2; suffix: " " + root.t("settings.unit_seconds") }
                }
                SettingTextArea {
                    key: "ai_custom_prompt"
                    label: root.t("settings.ai_prompt_label")
                    placeholder: root.t("settings.ai_prompt_placeholder")
                    hint: root.t("settings.ai_prompt_hint")
                }
            }
        }

        // ==========================================
        // TAB 2: PERFORMANCE & NETWORK
        // ==========================================
        Column {
            width: parent.width
            spacing: 18
            visible: root.activeSubTab === 2

            SettingCard {
                iconGlyph: Icons.database
                title: root.t("settings.cache_card_title")
                description: root.t("settings.cache_desc")
                SettingSwitch {
                    key: "use_cache"
                    label: root.t("settings.use_cache_checkbox")
                    description: root.t("settings.use_cache_desc")
                }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 12
                    Label {
                        Layout.fillWidth: true
                        text: root.t("settings.cache_count").replace("{count}", appBackend ? appBackend.cacheEntryCount : 0)
                        color: clrTxt
                        font.pixelSize: 13
                        font.bold: true
                    }
                    Button {
                        text: "🗑️ " + root.t("settings.cache_clear_btn")
                        topInset: 0; bottomInset: 0; leftInset: 0; rightInset: 0
                        enabled: Boolean(appBackend && appBackend.cacheEntryCount > 0 && !appBackend.isBusy)
                        onClicked: clearCacheDialog.open()
                    }
                }
            }

            SettingCard {
                iconGlyph: Icons.zap
                title: root.t("settings.perf_card_title")
                SettingSlider {
                    key: "batch_size"; label: root.t("settings.batch_size_title"); hint: root.t("settings.batch_size_hint")
                    from: 10; to: 500; stepSize: 10
                }
            }

            SettingCard {
                iconGlyph: Icons.gauge
                title: root.t("settings.network_card_title")
                description: root.t("settings.network_card_desc")
                SettingSlider {
                    key: "max_concurrency"; label: root.t("settings.concurrency_label"); hint: root.t("settings.concurrency_hint")
                    from: 1; to: 32; stepSize: 1
                }
                GridLayout {
                    Layout.fillWidth: true
                    columns: 2
                    columnSpacing: 24
                    rowSpacing: 8
                    SettingSlider { key: "rate_limit_delay"; label: root.t("settings.request_delay_label"); from: 0; to: 3; stepSize: 0.05; decimals: 2; suffix: " " + root.t("settings.unit_seconds") }
                    SettingSlider { key: "request_timeout"; label: root.t("settings.request_timeout_label"); from: 5; to: 120; stepSize: 5; suffix: " " + root.t("settings.unit_seconds") }
                    SettingSlider { key: "max_retries"; label: root.t("settings.max_retries_label"); from: 1; to: 10; stepSize: 1 }
                    SettingSlider { key: "max_chars_per_request"; label: root.t("settings.max_chars_label"); from: 500; to: 20000; stepSize: 500 }
                }
                SettingSwitch { key: "use_multi_endpoint"; label: root.t("settings.multi_endpoint_checkbox"); description: root.t("settings.multi_endpoint_desc") }
                SettingSwitch { key: "lingva_fallback"; label: root.t("settings.lingva_checkbox"); description: root.t("settings.lingva_desc") }
                SettingSwitch { key: "aggressive_retry"; label: root.t("settings.aggressive_retry_checkbox"); description: root.t("settings.aggressive_retry_desc") }
            }

            SettingCard {
                iconGlyph: Icons.globe
                title: root.t("settings.proxy_card_title")
                description: root.t("settings.proxy_card_desc")
                SettingSwitch { key: "proxy_enabled"; label: root.t("settings.proxy_enabled_checkbox") }
                SettingTextArea {
                    key: "proxy_list"
                    label: root.t("settings.proxy_list_label")
                    placeholder: "http://user:pass@1.2.3.4:8080\nsocks5://5.6.7.8:1080"
                    hint: root.t("settings.proxy_list_hint")
                }
            }
        }

        // ==========================================
        // TAB 3: TERMINOLOGY & MEMORY
        // ==========================================
        Column {
            width: parent.width
            spacing: 18
            visible: root.activeSubTab === 3

            SettingCard {
                iconGlyph: Icons.bookOpen
                title: root.t("settings.glossary_title")
                description: root.t("settings.glossary_desc")

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10
                    TextField {
                        id: glossaryTermInput
                        Layout.fillWidth: true
                        Layout.preferredHeight: Theme.heightInput
                        placeholderText: root.t("settings.glossary_term_placeholder")
                        color: clrTxt
                        placeholderTextColor: Theme.textMuted
                        background: Rectangle {
                            radius: Theme.radiusControl
                            color: clrInput
                            border.color: glossaryTermInput.activeFocus ? Theme.borderFocus : Theme.borderControl
                            border.width: 1
                        }
                    }
                    Label { text: "→"; color: clrTxtDim; font.pixelSize: 16 }
                    TextField {
                        id: glossaryReplacementInput
                        Layout.fillWidth: true
                        Layout.preferredHeight: Theme.heightInput
                        placeholderText: root.t("settings.glossary_replacement_placeholder")
                        color: clrTxt
                        placeholderTextColor: Theme.textMuted
                        background: Rectangle {
                            radius: Theme.radiusControl
                            color: clrInput
                            border.color: glossaryReplacementInput.activeFocus ? Theme.borderFocus : Theme.borderControl
                            border.width: 1
                        }
                        onAccepted: glossaryAddBtn.clicked()
                    }
                    Button {
                        id: glossaryAddBtn
                        Layout.preferredHeight: Theme.heightInput
                        enabled: glossaryTermInput.text.trim().length > 0 && glossaryReplacementInput.text.trim().length > 0
                        scale: down ? 0.98 : 1.0

                        background: Rectangle {
                            radius: Theme.radiusControl
                            color: glossaryAddBtn.enabled ? (glossaryAddBtn.hovered ? Theme.accentHover : Theme.accentSolid) : Theme.surfaceControl
                            border.color: glossaryAddBtn.enabled ? "transparent" : Theme.borderControl
                            border.width: 1
                            opacity: glossaryAddBtn.enabled ? 1.0 : 0.5
                        }

                        contentItem: RowLayout {
                            spacing: 6
                            anchors.centerIn: parent
                            Text { text: "➕"; font.pixelSize: 12 }
                            Text {
                                text: root.t("settings.glossary_add_btn")
                                font.pixelSize: 13
                                font.bold: true
                                color: glossaryAddBtn.enabled ? Theme.accentContrastText : Theme.textMuted
                            }
                        }

                        onClicked: {
                            if (!appBackend) return;
                            appBackend.addGlossaryTerm(glossaryTermInput.text, glossaryReplacementInput.text);
                            glossaryTermInput.text = "";
                            glossaryReplacementInput.text = "";
                            glossaryTermInput.forceActiveFocus();
                        }
                    }
                }

                Label {
                    visible: !appBackend || appBackend.glossaryTerms.length === 0
                    text: root.t("settings.glossary_empty")
                    color: clrTxtDim
                    font.pixelSize: 12
                }

                Repeater {
                    model: appBackend ? appBackend.glossaryTerms : []
                    delegate: Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: 40
                        radius: Theme.radiusControl
                        color: clrInput
                        border.color: clrCardBorder
                        border.width: 1
                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 12
                            anchors.rightMargin: 6
                            spacing: 10
                            Label { Layout.preferredWidth: 1; Layout.fillWidth: true; text: modelData.term; color: clrTxt; font.pixelSize: 13; elide: Text.ElideRight }
                            Label { text: "→"; color: clrTxtDim }
                            Label { Layout.preferredWidth: 1; Layout.fillWidth: true; text: modelData.replacement; color: clrAccent; font.pixelSize: 13; elide: Text.ElideRight }
                            ToolButton {
                                text: "🗑️"
                                ToolTip.visible: hovered
                                ToolTip.text: root.t("settings.glossary_remove")
                                onClicked: { if (appBackend) appBackend.removeGlossaryTerm(modelData.term); }
                            }
                        }
                    }
                }
            }

            SettingCard {
                iconGlyph: Icons.lock
                title: root.t("settings.protected_card_title")
                description: root.t("settings.protected_card_desc")
                SettingTextArea {
                    key: "protected_terms"
                    placeholder: root.t("settings.protected_terms_placeholder")
                }
            }

            SettingCard {
                iconGlyph: Icons.brain
                title: root.t("settings.tm_card_title")
                description: root.t("settings.tm_card_desc")
                SettingSwitch { key: "tm_enabled"; label: root.t("settings.tm_enabled_checkbox") }
                SettingTextArea {
                    key: "tm_files"
                    label: root.t("settings.tm_files_label")
                    hint: root.t("settings.tm_files_hint")
                    minLines: 3
                }
                Button {
                    text: "📂 " + root.t("settings.tm_add_file_btn")
                    topInset: 0; bottomInset: 0; leftInset: 0; rightInset: 0
                    onClicked: tmFileDialog.open()
                }
                SettingSwitch { key: "tm_fuzzy"; label: root.t("settings.tm_fuzzy_checkbox"); description: root.t("settings.tm_fuzzy_desc") }
                SettingSlider {
                    visible: Boolean(appBackend && appBackend.settings["tm_fuzzy"])
                    key: "tm_fuzzy_threshold"; label: root.t("settings.tm_threshold_label")
                    from: 0.5; to: 1.0; stepSize: 0.01; decimals: 2
                }
            }
        }
    }

    FileDialog {
        id: tmFileDialog
        title: root.t("settings.tm_add_file_btn")
        nameFilters: ["TMX / CSV / TSV / JSON / XUnity (*.tmx *.csv *.tsv *.json *.txt)"]
        onAccepted: { if (appBackend) appBackend.addTranslationMemoryFile(selectedFile); }
    }

    Dialog {
        id: clearCacheDialog
        anchors.centerIn: Overlay.overlay
        modal: true
        title: root.t("settings.cache_clear_confirm_title")
        standardButtons: Dialog.Yes | Dialog.Cancel
        Label {
            width: 380
            wrapMode: Text.WordWrap
            text: root.t("settings.cache_clear_confirm")
            color: clrTxt2
        }
        onAccepted: { if (appBackend) appBackend.clearCache(); }
    }
}
