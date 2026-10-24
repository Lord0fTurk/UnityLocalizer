# Changelog — UnityLocalizer

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

## [0.2.0] - 2026-10-24

### Added
- **Automatic Source-Language Detection**:
  - New `src/core/lang_detect/` package resolves `Auto-detect` before translation starts: Unicode script analysis (Han, kana, Hangul, Thai, Hebrew, Greek) → offline `py3langid` model (≥ 90% confidence over a spread of prose lines) → Google majority vote for keyless engines (Google/Bing; users of private or paid engines never send text to Google).
  - The detected code now drives the engine request, CSV/TSV column selection (loose tables are re-harvested when the language differs from English) and XUnity `FromLanguage`, so Chinese, Japanese, Korean and Russian games no longer run as "assumed English".
  - `py3langid` added to requirements, PyInstaller collection and `--self-check`.
- **User Notifications for Important Events**:
  - Progress events listed in `NOTIFICATION_LEVELS` now raise a toast and a warning/info log entry: detected game language (offline or online), failed detection, unknown Unity version and missing font glyphs.
  - Source-language label simplified from "Auto-detect (assumes English)" to "Auto-detect" in all 12 UI languages.
- **Universal Multi-Theme & Accent Preset UI System**:
  - Introduced unified reactive QML theme singleton (`Theme.qml`) implementing the 3-theme token matrix: **Obsidian** (Default Dark), **Daylight** (Soft White), and **Cyber Neon** (High-Contrast Glow).
  - Integrated 4 distinct accent color presets: **Cyan/Teal** (Modern), **Emerald/Mint** (Nature), **Indigo/Violet** (Creative), and **Amber/Orange** (Energetic).
  - Developed reusable UI archetype components (`PrimaryButton.qml`, `SecondaryButton.qml`, `SegmentedToggle.qml`, `SectionCard.qml`, `QuickTag.qml`).
  - Refactored all views (`Main.qml`, `DashboardView.qml`, `ToolboxView.qml`, `SettingsView.qml`, `ConsoleView.qml`, `EditorView.qml`, `AboutView.qml`) to eliminate hardcoded palette properties in favor of semantic tokens.
  - Added interactive Appearance & Theme management card in Settings, with full i18n coverage across all 12 supported languages.
- **High-Performance In-Memory Regex Caching & FairyGUI Support**:
  - Activated `CacheRegexPatternResults=True` in BepInEx AutoTranslator configuration, caching compiled regex outcomes in memory to prevent micro-stuttering and preserve 60+ FPS during heavy text scenes.
  - Lowered `MinDialogueChars=1` to capture single-character menu buttons (`+`, `-`, `X`, `?`, `!`, `1`).
  - Added native `EnableFairyGUI=True` framework hooking for Asian and mobile-ported Unity titles.
- **Runtime Glossary Terminology Injection (`_Substitutions.txt`)**:
  - Automated deployment of user glossary terms to `Translation/{Lang}/Text/_Substitutions.txt`.
  - Ensures recurring character names, factions, and RPG terms are consistently replaced at runtime even when concatenated dynamically in C# code.
- **Bilingual / Comparative Translation Mode**:
  - Full support for dual-language display (`{target}\n({source})`), allowing players and QA reviewers to view translated text alongside original dialogue and item names.
- **Native Taskbar & Window Icon Identity**:
  - Implemented Win32 native `WM_SETICON` message dispatcher and `SetCurrentProcessExplicitAppUserModelID` in launcher bootstrap, ensuring taskbar and titlebar display application brand icon instead of blank generic window on Windows.
- **Modern Vector Icon System & Community Support**:
  - Replaced emoji glyphs (`🎮`, `🏠`, `🧰`, `⚙️`, etc.) with vector Lucide icon font subset (`UnityLocalizerIcons.ttf`, `Icons.qml`, `Icon.qml`, `IconLabel.qml`).
  - Upgraded top-left sidebar header by rendering genuine `icon.png` application branding via `AppBackend.get_asset_url`.
  - Added dedicated Patreon support button with animated scale feedback and glowing neon heart icon (`Icons.heart`) in sidebar navigation, with 100% localization across all 12 supported languages (`tr`, `en`, `de`, `es`, `fr`, `ru`, `pt-BR`, `ja`, `zh-CN`, `ko`, `it`, `fa`).
- **Intelligent IL2CPP & Unity 6 Runtime Optimization**:
  - Automated OS TrueType system font fallback (`OverrideFontTextMeshPro` with Arial, SimHei, Meiryo, Malgun Gothic, Segoe UI) on IL2CPP builds, completely eliminating stripped runtime AssetBundle crashes (`AssetBundle::LoadFromFile_Internal`).
  - Automated disabling of unsupported IMGUI hooks (`EnableIMGUI=False`) on IL2CPP games, preventing console `NotImplementedException` spam.
- **Dynamic Choice & Option Prefix Regex Engine**:
  - Advanced regex generator (`xunity_regex.py`) producing prefix-preserving `.NET` regex rules for dialogue buttons and menu options.
  - Transparently translates numbered options (`1. `, `(2) `, `[3] `), bullet points (`- `, `> `), and CRPG skill/roleplay check tags (`[Charm] `, `[Strength 14] `, `[Lie] `) that are dynamically concatenated at runtime.
- **Comprehensive Font Manager (uGUI & TextMeshPro)**:
  - Full support for `OverrideFont` targeting legacy uGUI (`UnityEngine.UI.Text`) in addition to TextMeshPro SDF fallback bundles.
  - Custom font installer (`FontBootstrap.install_custom_font`) allowing users to provide custom `.ttf` or `.otf` fonts (e.g. pixel, gothic, or stylistic fonts) copied into `BepInEx/fonts/`.
  - Exported patch payload automatically bundles custom fonts located under `BepInEx/fonts/`.
  - Toolbox UI upgraded with interactive preset selector: Standard TMP SDF bundle, Custom TTF/OTF font file with file picker, and System Font override.
  - Settings schema extended with `custom_font_path`, `override_font_ugui`, and `font_preset`.
- **Linux & Steam Deck (Proton) Support**:
  - Exported standalone patches now include native POSIX shell scripts (`Install_Patch.sh`, `Uninstall_Patch.sh`, `Yama_Kur.sh`, `Yama_Kaldir.sh`) with POSIX LF line endings.
  - Interactive Steam Deck and Linux Proton guidance automatically embedded in installer shell output and `README.txt` / `BENI_OKU.txt` (`WINEDLLOVERRIDES="winhttp=n,b" %command%`).
  - `EngineProfiler` extended to detect Linux Unity binaries (`.x86_64`, `.x86`, and extensionless binaries matching `*_Data`), parsing ELF headers for 32/64-bit architecture.
  - Root `pytest.ini` configuring `pythonpath = .` for seamless test runs.
- **Interactive Completion Summary Modal & One-Click Game Launcher**:
  - Implemented sleek desktop completion modal (`CompletionDialog.qml`) displaying key post-run metrics (translated line count, success rate, total strings, target language, destination path).
  - Added non-blocking one-click game launch capability (`AppBackend.launchGame`) directly from the completion dialog.
  - Provided direct shortcuts to review translation rows in the Editor tab and open destination folders in the OS file manager.

### Changed
- **Humanized Translation Action Labels & Explanatory Hints**:
  - Replaced mechanical "Yerelleştirme İş Hattı" / "Localization Pipeline" phrasing with intuitive "Otomatik Çeviri & Yama Süreci" / "Çeviriyi Başlat ve Yamayı Kur" ("Start Translation & Deploy Patch") across all 12 supported languages.
  - Added descriptive process guide explaining that text is extracted, translated with the selected engine, and deployed directly as an offline game patch.
- **Active Game Workspace Banner**:
  - Transformed the empty drop zone into a rich game card displaying project title, vector gamepad avatar (`Icons.gamepad2`), active status pill (`Icons.circleCheck`), directory path, and quick actions ("Klasörü Aç" and "Farklı Oyun Seç...").
- **Button Geometry & Inset Normalization**:
  - Zeroed Qt Material default insets (`topInset: 0`, `bottomInset: 0`, `leftInset: 0`, `rightInset: 0`, `padding: 0`) across all button components, quick tags, and custom action delegates to guarantee exact declared height/padding and prevent background rectangle shrinkage.
- **Segmented Sub-Tabs Bar & Desktop UI Polish**:
  - Refactored Settings sub-tabs from loose tag elements into a grounded, cohesive Segmented Tab Bar container utilizing vector icons (`Icons.monitor`, `Icons.bot`, `Icons.zap`, `Icons.bookOpen`).
  - Replaced theme mode and accent color plain toggles with rich 44px option tiles featuring distinct active selection fills, color swatches, and active checkmark badges (`Icons.circleCheck`).
  - Purged OS emoji glyphs across all view screens (`DashboardView`, `ToolboxView`, `SettingsView`, `ConsoleView`, `EditorView`, `AboutView`) in favor of pixel-perfect vector Lucide glyphs.

### Fixed
- **Extended Unity Version Tag & Custom Build Detection**:
  - Enhanced Unity version regex parser in `EngineProfiler` to seamlessly recognize custom, LTS, and regional China build tags (e.g., `2021.3.45f2c1`), ensuring matching TMP SDF fallback font bundles (`arialuni_sdf_u2021`) are accurately provisioned.
- **Large Bundle CSV/JSON Field Limit Handling**:
  - Increased `csv.field_size_limit` to system maximum with safe `csv.Error` fallbacks in `loc_table.py`, preventing crashes when extracting large compiled JSON/text data from game asset bundles.
- **QML Completion Modal Signal Serialization**:
  - Resolved `undefined` metric properties in `CompletionDialog.qml` by typing the `pipelineCompleted` signal as native `QVariantMap` in `AppBackend` and introducing safe null-coalescing number and string helpers.
- **Dialogue & Dynamic Quote Variant Dual-Emission**:
  - Added intelligent dialogue speaker stripping (`{0}: `, `[Speaker]: `, `Name: `) and typographic quote normalization (`'`, `’`, `…`, `...`) in `auto_translator.py`, ensuring spoken dialogue and menu choices hook seamlessly into XUnity AutoTranslator runtime lookups.
- **Modern Unity & Unity 6 Runtime Hook Optimizations**:
  - Configured `EnableTranslationScoping=False`, `IgnoreVirtualTextSetterCallingRules=True`, and `ForceMonoModHooks=True` in AutoTranslator bootstrap to bypass TextMeshPro virtual setter constraints on modern .NET runtimes.
- **Patreon Support Link**:
  - Corrected sidebar Patreon navigation redirect to point to the active project page (`https://www.patreon.com/cw/LordOfTurk`).
- **Accent Color Selector Property Scope**:
  - Fixed property resolution scoping error (`TypeError: Cannot read property 'r' of undefined`) in Settings accent color button delegate by binding hex color values directly to the button component scope.

## [0.1.0] - 2026-10-19

Initial open-source release of **UnityLocalizer**, an autonomous desktop translation and localization automation suite for games built on the Unity engine.

### Added
- **Multi-Channel Text Harvesting**:
  - Read-only asset extraction using `UnityPy` across `level*`, `*.assets`, `data.unity3d`, and loose/Addressable `AssetBundle` archives.
  - TypeTree-aware field extraction for Unity Localization (`StringTable`), I2 Localization (`LanguageSourceData`), and Pixel Crushers `DialogueDatabase`.
  - Static IL2CPP string literal pool harvesting from `il2cpp_data/Metadata/global-metadata.dat`.
  - Static Mono assembly string literal extraction from the `#US` (User String) stream of `Managed/Assembly-CSharp.dll` without executing game binaries.
  - Loose `StreamingAssets` parsing for JSON, CSV, TSV, XML, plain text, Yarn Spinner (`.yarn`), Inkle Ink (`.ink.json`), and Naninovel (`.nani`) scripts.
  - Shared heuristic text filter (`harvesters/text_filter.py`) automatically skipping code identifiers, GUIDs, shader names, namespaces, and technical asset paths.
- **AST Syntax Guard & Placeholder Isolation**:
  - Tokenization and strict preservation of Unity RichText tags (`<color>`, `<size>`, `<b>`, `<i>`, `<sprite>`), NGUI BBCode (`[ff0000]`), and C# string formatting patterns (`{0}`, `{playerName}`, `\n`, `%s`).
  - Automated word-boundary token repair for dropped standalone placeholders.
  - Multiset integrity gate preventing broken tags or format mismatches from corrupting game logic.
- **Autonomous Runtime Hook Deployment (Route 3)**:
  - Automated deployment of BepInEx 5.4.23.5 (Mono) or BepInEx 6 (IL2CPP; v6.0.0-pre.2 for metadata v23–v29, Bleeding-Edge build 764 for Unity 6 / metadata v30+).
  - Pre-configured `XUnity.AutoTranslator` (v5.6.2) running strictly as an offline dictionary loader (`Endpoint=` empty).
  - Version-matched ArialUnicode SDF fallback font bundle provisioning to `BepInEx/font/` resolving missing TextMeshPro glyphs ("tofu" boxes).
  - Dynamic `.NET` regex dictionary generation (`r:"pattern"="replacement"`) in `UnityLocalizer.txt` translating formatted runtime strings (`Gold: {0}`).
  - Non-destructive `AutoTranslatorConfig.ini` line-preserving merge updating only managed keys while preserving user custom configurations.
- **Translation Engine Integrations**:
  - Multi-mirror Google Translate with 13 endpoints, `batchexecute`, IP circuit breaker, and Lingva fallback.
  - Keyless Microsoft Edge Bing translator with automatic request chunking and exponential backoff.
  - DeepL Free and Pro API support with formality level control.
  - Self-hosted and public LibreTranslate API integration.
  - AI translation backends: Google Gemini (`google-genai`), OpenAI, DeepSeek, and OpenAI-compatible endpoints (OpenRouter) with structured XML batching.
  - Local LLM support via Ollama and LM Studio endpoints.
- **Offline Patch Exporter**:
  - One-click export packaging standalone offline translation patches (`.zip` and structured folder) into `%APPDATA%/UnityLocalizer/Patches`.
  - Manifest-based Turkish and English one-click installation and restoration scripts (`Yama_Kur.bat`, `Yama_Kaldir.bat`, `Install_Patch.bat`, `Uninstall_Patch.bat`).
  - Preflight checks ensuring hook presence and translation availability before packaging.
- **Interactive Review Editor**:
  - Visual review table displaying rejected, repaired, failed, edited, accepted, and unchanged strings.
  - Manual in-place editing with immediate Syntax Guard validation.
  - Direct "Save to Game" action applying reviewed translations directly to game runtime dictionaries and loose files.
- **Terminology, Memory & RTL Support**:
  - Customizable glossary terms with literal tag-safe replacements.
  - Multi-format translation memory loader (TMX, CSV, TSV, JSON, TXT) with token-bucketed fuzzy matching (`rapidfuzz`).
  - Static RTL shaping and bidirectional text reordering for Arabic, Persian, Hebrew, Urdu, Pashto, Sorani, Sindhi, Uyghur, Yiddish, and Dhivehi.
- **Modern PyQt6 & Qt Quick Desktop UI**:
  - Cyberpunk-inspired dark glassmorphic interface with 12 UI languages (`tr`, `en`, `de`, `es`, `fr`, `ru`, `pt-BR`, `ja`, `zh-CN`, `ko`, `it`, `fa`).
  - Real-time logging console, background worker execution, non-blocking cancellation, and persistent window geometry and settings schema.
- **Security & Reliability Hardening**:
  - Path traversal and script injection protections across language codes, patch exporters, and batch files (`DisableDelayedExpansion`).
  - Billion Laughs XML entity expansion guards on all XML and TMX parsers.
  - Real-time API key, bearer token, and proxy credential masking in all logger and UI outputs.
  - Thread-safe SQLite translation cache with Write-Ahead Logging (WAL) and SHA256 deterministic keying.
  - Frozen application self-check (`run.py --self-check`) verifying runtime dependencies and asset packages.
