# Changelog — UnityLocalizer

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.2.0] - 2026-10-26

### Added
- **Automatic Source-Language Detection**:
  - New `src/core/lang_detect/` package resolves `Auto-detect` before translation starts: Unicode script analysis (Han, kana, Hangul, Thai, Hebrew, Greek) → offline `py3langid` model (≥ 90% confidence over a spread of prose lines) → Google majority vote for keyless engines (Google/Bing; users of private or paid engines never send text to Google).
  - The detected code now drives the engine request, CSV/TSV column selection (loose tables are re-harvested when the language differs from English) and XUnity `FromLanguage`, so Chinese, Japanese, Korean and Russian games no longer run as "assumed English".
  - Detector answers are mapped to the language catalog (`canonical_language_code`: `zh` → `zh-CN`, `iw` → `he`, ...); the Google mirrors gained a `detect_language` call for the online vote.
  - When a game only ships non-English Unity Localization tables, the locale of those tables is used as the source language (`source_detected_tables` notice), and the harvest is repeated for that language whenever table or record content depends on it.
  - `py3langid` added to requirements, PyInstaller collection and `--self-check` (which also verifies the offline model).
- **Automatic Runtime Setup (no install button)**:
  - "Start translation" now checks and, when needed, downloads and installs the matching BepInEx + XUnity package for the game's Mono/IL2CPP flavor and 32/64-bit build (SHA256-pinned downloads) and shows only a "preparing components" status. The manual install buttons were removed from the Dashboard and Toolbox (uninstall stays).
  - `BepInEx/UnityLocalizer.runtime.json` records the installed package; a hand-installed hook of the right generation is kept, a mismatching one is replaced. After a run, `BepInEx/LogOutput.log` is inspected ("Chainloader startup complete", XUnity, `[Fatal]`/`[Error]`) and the result is reported.
  - Clear, localized failure reasons (network, integrity, permission, unsupported build) instead of a generic error; a build whose bitness could not be determined is flagged.
- **Dashboard Notices Card**: warnings and important results (language detection, unreadable files, glyph coverage, runtime log, Proton/Linux hints, anti-mod detection) are shown on the Dashboard (Turkish tab name "Ana Sayfa"), not only in the log; the card is cleared when a new run starts.
- **Harvest Coverage Report & Deeper Extraction**:
  - `HarvestStats` records files scanned or failed, raw-scanned objects, Unity Localization tables matched or skipped by locale, I2 sources and encrypted code; a summary is written to `harvest_report.json` and unreadable files, raw scans and encrypted code raise warnings.
  - New `localization` channel for loose folders named like `Localization`, `Lang`, `Dialog`, `Text`, `i18n`, `Subtitle`, `Story`; extra AssetBundles (`.bundle`, `.unity3d`, `.assetbundle`, `.ab` with UnityFS magic), `mainData`, `.split0` parts; subtitles (`.srt`) and .NET resources (`.resx`); single CJK characters in menus; JSON with raw line breaks inside strings.
- **Source-Language Filtering of Multi-Language Games**: JSON records that carry every language side by side (`english_text`, `chinese_text`, `korea_text`, ...) keep only the source-language field, and strings in a script foreign to the source language (Cyrillic, Han, kana, Hangul, Thai...) are left out, with a guard that keeps everything and warns when the source-language setting looks wrong. Project XX Queen: 94,017 → 17,891 strings.
- **Anti-Mod Warning**: some games ship code that deletes BepInEx at start (Project XX Queen Demo has `BepInExRemover` / `CheckAndRemoveBepInEx`: the folders vanish about 10 seconds after launch and the game quits, so no translation can appear). The pipeline reads class and method names from `Assembly-CSharp*.dll` / `global-metadata.dat` before translating and warns in 12 languages. Detection is read-only; the tool does not work around the game's protection.
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
  - Sidebar "Support the developer" button (12 languages, "Patreon" sub-line): warm pink instead of error red, centred content and a slow heartbeat on the heart icon that quickens on hover.
  - The completion dialog shows a small support row with a "Don't show again" checkbox from the 3rd finished run (`completed_runs`, `hide_support_prompt`); never on the first runs.
- **Intelligent IL2CPP & Unity 6 Runtime Optimization**:
  - On IL2CPP builds (stripped AssetBundle loading) an installed OS system font (Arial, SimHei, Meiryo, Malgun Gothic, Segoe UI by language) is added through XUnity's `FallbackFontTextMeshPro` for missing glyphs only, avoiding the `AssetBundle::LoadFromFile_Internal` crashes. `OverrideFontTextMeshPro` is never used there: it crashed a Unity 6000 game.
  - Automated disabling of unsupported IMGUI hooks (`EnableIMGUI=False`) on IL2CPP games, preventing console `NotImplementedException` spam.
- **Dynamic Choice & Option Prefix Regex Engine**:
  - Advanced regex generator (`xunity_regex.py`) producing prefix-preserving `.NET` regex rules for dialogue buttons and menu options.
  - Transparently translates numbered options (`1. `, `(2) `, `[3] `), bullet points (`- `, `> `), and CRPG skill/roleplay check tags (`[Charm] `, `[Strength 14] `, `[Lie] `) that are dynamically concatenated at runtime.
  - With the cap at 3000 entries, short UI templates are written before long library diagnostics and 500 slots stay reserved for choice prefixes.
- **Comprehensive Font Manager (uGUI & TextMeshPro)**:
  - Full support for `OverrideFont` targeting legacy uGUI (`UnityEngine.UI.Text`) in addition to TextMeshPro SDF fallback bundles.
  - Custom font installer (`FontBootstrap.install_custom_font`) allowing users to provide custom `.ttf` or `.otf` fonts (e.g. pixel, gothic, or stylistic fonts) copied into `BepInEx/fonts/`.
  - Exported patch payload automatically bundles custom fonts located under `BepInEx/fonts/`.
  - Toolbox UI upgraded with interactive preset selector: Standard TMP SDF bundle, Custom TTF/OTF font file with file picker, and System Font override.
  - Settings schema extended with `custom_font_path`, `override_font_ugui`, and `font_preset`.
- **Linux & Steam Deck Support**:
  - Windows games under Proton: exported standalone patches include native POSIX shell scripts (`Install_Patch.sh`, `Uninstall_Patch.sh`, `Yama_Kur.sh`, `Yama_Kaldir.sh`) with POSIX LF line endings; the Dashboard shows the Proton launch hint (`WINEDLLOVERRIDES="winhttp=n,b" %command%`) when UnityLocalizer runs on Linux.
  - **Native Linux Unity builds (experimental)**: the Linux BepInEx packages (Mono x64/x86, IL2CPP pre.2 and be.764 x64; SHA256-pinned) are installed with `run_bepinex.sh`/`libdoorstop.so`, the executable name is set and the scripts are made executable; launch option `./run_bepinex.sh %command%`. There is no 32-bit Linux IL2CPP package, so such builds report "unsupported" instead of installing the wrong one. Verified only up to package download and checksums, not yet on a real Linux machine.
  - `EngineProfiler` detects Linux Unity binaries (`.x86_64`, `.x86`, ELF headers, `UnityPlayer.so`/`GameAssembly.so`) and 32/64-bit architecture.
  - Root `pytest.ini` configuring `pythonpath = .` for seamless test runs.
  - Running UnityLocalizer itself on Linux: `run.sh` launcher, README section with the Qt/xcb system packages (`libxcb-cursor0` ...) and font notes, and an `ubuntu-latest` CI job (tests, lint, self-check; reports without failing the workflow until it has been green once).
  - Experimental Linux release build: the release workflow gained a `build-linux` job (`ubuntu-22.04`, PyInstaller, `UnityLocalizer-<version>-linux-x64.tar.gz`) that only publishes when the frozen program passes its own `--self-check` and an offscreen start-up; `build.py` no longer passes the Windows `.ico` to PyInstaller on other platforms.
- **Interactive Completion Summary Modal & One-Click Game Launcher**:
  - Implemented sleek desktop completion modal (`CompletionDialog.qml`) displaying key post-run metrics (translated line count, success rate, total strings, target language, destination path).
  - Added non-blocking one-click game launch capability (`AppBackend.launchGame`) directly from the completion dialog.
  - Provided direct shortcuts to review translation rows in the Editor tab and open destination folders in the OS file manager.
- **Review Editor**:
  - Opens the dictionary already in the selected game when no run is being reviewed (after a restart, or for a game translated earlier): problems first, derived variants left out so each text appears once; a run that just finished for the same game is kept. Right-to-left targets are not opened this way because their dictionary holds shaped text.
  - Rebuilt around an in-memory SQLite index (`review_store.py`): the list is **paged** (50 per page), so every row of a 30,000+ line dictionary is reachable instead of only the first 500.
  - **Search folds case and diacritics, including Turkish i/I/ı/İ** (`text_fold.py`): "isik" finds "ışık", "istanbul" finds "İstanbul".
  - **Detail panel** with the source, the tags and placeholders it must keep, the translation box with a **live format check**, **Revert** and **Apply & next** (Ctrl+Enter); changed rows are marked; new "Changed" and "With issues" filters.
  - **Find & Replace** over the rows matching the current filter and search; tags and placeholders are never touched and every changed row goes through the format check.

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
  - Purged OS emoji glyphs across all view screens, search fields, toasts and the editor error row in favor of pixel-perfect vector Lucide glyphs (system emoji were colour-inconsistent on Windows and missing on Linux/Steam Deck).
- **Completion dialog** is slightly wider so action labels are cut less.
- **Documentation**: README no longer mentions the removed "Install Hooks" button, describes the IL2CPP fallback font and marks native Linux as experimental, and has an FAQ entry for games that remove BepInEx; new `DESIGN.md` v3.0 (UI design-system specification: the 3 themes, 4 accent presets, radius scale and "zero-breakage" refactor rules) and `forum.md` (BBCode forum presentation template); `AGENTS.md` brought up to date.
- **Tests**: regression tests for every item above (532 tests), including the QML text coverage and i18n key checks for all 12 locales.

### Fixed
- **Linux: starting the game from the app**: the completion dialog's launch button ran the game binary directly, which never loads BepInEx on a native Linux game. It now starts `run_bepinex.sh` when the hook is installed, and a Windows game on a Linux host gets a clear message (start it from Steam with Proton) instead of a raw error (`game_launcher.py`).
- **Linux: TextMeshPro fallback font names**: the automatic fallback used Windows font names (Arial, SimHei, Meiryo, Malgun Gothic, Segoe UI), which a Linux or Steam Deck system does not have. Native Linux games now get Linux families (DejaVu Sans, Liberation Sans, Noto Sans, Noto Sans CJK, ...), chosen from the installed fonts when `fc-list` is available (`system_fonts.py`).
- **Patch scripts hid failures**: `Install_Patch.sh` and `Uninstall_Patch.sh` copied files in a loop at the end of a pipe, so a failing `cp` did not stop the script and it reported success. They now count failures, print each one and exit non-zero (tests run the generated scripts with a real `sh`).
- **Uninstall left the install behind**: the runtime marker now lists the top-level files and folders the installer added, and uninstall removes exactly those (`.doorstop_version`, the bundled `dotnet/` runtime of IL2CPP installs, proxy files); older installs are cleaned only for what is certainly BepInEx's. BepInEx's own `changelog.txt` is no longer extracted, so it cannot replace a game file of the same name.
- **IL2CPP games showed no translation at all**: `AutoTranslatorConfig.ini` was written with `ForceMonoModHooks=True`. XUnity's IL2CPP text hooks exist only as Harmony hooks, so every hook failed ("Harmony is not supported in this runtime"). The setting is forced to `False` (existing installs are corrected on the next run); extra `behaviour` keys no longer replace the other forced Behaviour keys. `EnableTranslationScoping=False` and `IgnoreVirtualTextSetterCallingRules=True` stay forced to bypass TextMeshPro virtual setter constraints on modern .NET runtimes.
- **No TextMeshPro font for Turkish and other Latin-extended text**: the Settings default (empty system font) was passed as `""`, which switched the font override off instead of choosing one automatically, so IL2CPP games kept a font without `ç ğ ı ş ö ü`. Empty now means automatic (see the IL2CPP fallback font above); a value written by an older run is cleared. Verified in Project_Dungeon (`ı ğ ç ö` render, no crash).
- **Texts with a stored `\n` stayed untranslated**: some games keep line breaks as the two characters backslash + n and convert them just before drawing, so XUnity saw a real line break and never matched the dictionary key. Every such entry now also gets a real-line-break variant (143 entries in Project_Dungeon, verified in game).
- **Runtime templates dropped at random**: only 1500 regex entries were written and the survivors were simply the first ones harvested, so in Project_Dungeon 1736 of 3236 placeholder templates and all 7357 choice-prefix entries were lost. The cap is now 3000 (measured: negligible load cost; the game started and translated as before).
- **Doubled icons and ⚠ prefixes**: the `export_patch_btn` and `harvest_assets_btn` strings carried a 📦 emoji although their buttons already draw a Lucide icon; the `quick_rtl_*` and `quick_lang_unsupported` strings carried ⚠/↔ prefixes. They are gone from all 12 locales.
- **App icon visibility**: `icon.png`/`icon.ico` were rebuilt so the controller glyph fills the badge (it used to sit small in a wide empty margin and disappeared at taskbar and title-bar sizes); the sidebar and About logos render at 128 px source size.
- **Editor rendering**: game text containing `<b>` or `<color=...>` is shown literally.
- **Extended Unity Version Tag & Custom Build Detection**:
  - Enhanced Unity version regex parser in `EngineProfiler` to seamlessly recognize custom, LTS, and regional China build tags (e.g., `2021.3.45f2c1`), ensuring matching TMP SDF fallback font bundles (`arialuni_sdf_u2021`) are accurately provisioned.
- **Large Bundle CSV/JSON Field Limit Handling**:
  - Increased `csv.field_size_limit` to system maximum with safe `csv.Error` fallbacks in `loc_table.py`, preventing crashes when extracting large compiled JSON/text data from game asset bundles.
- **QML Completion Modal Signal Serialization**:
  - Resolved `undefined` metric properties in `CompletionDialog.qml` by typing the `pipelineCompleted` signal as native `QVariantMap` in `AppBackend` and introducing safe null-coalescing number and string helpers.
- **Dialogue & Dynamic Quote Variant Dual-Emission**:
  - Added intelligent dialogue speaker stripping (`{0}: `, `[Speaker]: `, `Name: `) and typographic quote normalization (`'`, `’`, `…`, `...`) in `auto_translator.py`, ensuring spoken dialogue and menu choices hook seamlessly into XUnity AutoTranslator runtime lookups.
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
