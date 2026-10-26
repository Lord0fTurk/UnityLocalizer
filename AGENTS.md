# AGENTS.md — UnityLocalizer Architecture & Development Guide

> **AI Coding Assistant Orientation & Context**
> Last Updated: 2026-10-24 | Version: 0.2.0

---

## 1. Project Overview

**UnityLocalizer** is a high-performance, autonomous, desktop translation and localization automation suite for games built on the **Unity** engine.

Following the design legacy of its sister projects **RenLocalizer** (Ren'Py) and **RPGMLocalizer** (RPG Maker & WOLF RPG), UnityLocalizer provides **ahead-of-time (AOT) batch translation and patch deployment**: translation uses the selected engine once, and the deployed patch runs fully offline.

### Key Capabilities
- **Read-only harvest, two delivery routes** (`EngineProfiler._determine_routes`):
  - **Harvest channels**: serialized assets (`level*`, `*.assets`, `data.unity3d`, AssetBundles) via read-only `UnityPy` (TypeTree-aware for Unity Localization `StringTable`, I2 `LanguageSourceData`, Dialogue System; raw length-prefixed scan otherwise), code literals (Mono `#US` stream / IL2CPP `global-metadata.dat`), and loose `StreamingAssets` files (`.json`, `.csv`, `.tsv`, `.xml`, `.txt`, `.yarn`, `.nani`, compiled Ink). "Route 2" (read-only asset extraction) is this harvest, not a separate delivery mechanism.
  - **Route 1 (Native Static Patcher, opt-in)**: rewrites loose `StreamingAssets` files in place (`patch_loose_files`, `.bak` originals, re-runs always read the `.bak`).
  - **Route 3 (Runtime Hook, always recommended)**: BepInEx 5 (Mono) / BepInEx 6 (IL2CPP) + `XUnity.AutoTranslator` as an offline dictionary loader (`Endpoint=` empty). Asset and code text can only reach the game this way. `has_bepinex` means proxy DLL + `BepInEx/core` + XUnity plugin (`src/core/hook_layout.py`), never just a `BepInEx` folder.
  - **XUnity facts (verified in its source)**: it loads every `*.txt` below `Directory` (keep `Translation\{Lang}\Text`); `_`-prefixed files and the OutputFile ignore regex entries, and the OutputFile has the lowest priority and is pruned on startup, so we write `UnityLocalizer.txt`; an unescaped `//` anywhere in a line is a comment; `%3D` decodes to `=`; `r:"pattern"="replacement"` entries are tried only when no direct lookup matches (`match.Result`, so `${N}`/`$$`).
- **Comprehensive Font Management (uGUI & TMP SDF)**: Solves the missing glyph / "tofu" (□) crisis across both legacy `UnityEngine.UI.Text` (via `OverrideFont` and custom `.ttf`/`.otf` font installation to `BepInEx/fonts/`) and TextMeshPro (via prebuilt ArialUnicode SDF AssetBundle deployed to `BepInEx/font/` as `FallbackFontTextMeshPro` or `OverrideFontTextMeshPro` for system fonts).
- **Dynamic Choice & Prefix Regex (`xunity_regex.py`)**: Automatically produces prefix-preserving `.NET` regexes for runtime-numbered dialogue choices (`1. `, `[1] `) and CRPG skill tags (`[Charm] `, `[Strength] `), ensuring choices translate in-game even when formatted dynamically.
- **IL2CPP & Unity 6 Runtime Optimization (`font_bootstrap.py`)**: Automatically selects OS TrueType fonts (`OverrideFontTextMeshPro`) on IL2CPP builds to avoid stripped `AssetBundle.LoadFromFile_Internal` crashes, and disables unsupported IMGUI hooks (`EnableIMGUI=False`).
- **Linux & Steam Deck Ready**: Exported patch packages include native POSIX shell scripts (`Install_Patch.sh`, `Uninstall_Patch.sh`) alongside Windows `.bat` scripts, providing automated instructions for Steam Deck Proton launcher overrides (`WINEDLLOVERRIDES="winhttp=n,b" %command%`). EngineProfiler also detects Linux `.x86_64` executables and ELF headers.
- **Automatic Source-Language Detection** (`src/core/lang_detect/`): when the source language is `auto`, the pipeline detects the game's language right after harvesting: Unicode script counting (Han/kana/Hangul/Thai/Hebrew/Greek) -> offline `py3langid` model (confidence >= 0.90, spread of prose lines) -> Google majority vote (keyless engines only, so users of private/paid engines keep text local). The detected code feeds the engine, CSV column selection and XUnity `FromLanguage`; when nothing is certain the run keeps `auto`/English and the user gets a warning toast.
- **User Notifications** (`NOTIFICATION_LEVELS` in `src/core/progress.py`): progress events listed there become toast + warning/info log entries (language detection result, glyph coverage, unknown Unity version) instead of silent console lines.
- **AST Syntax Guard**: Tokenizes Unity RichText tags (`<color>`, `<size>`, `<b>`, `<sprite>`) and C# formatting patterns (`{0}`, `{playerName}`, `\n`) into immutable placeholders before translation and validates them upon restoration.
- **RenLocalizer Translation Engines**: Integrates battle-tested multi-mirror Google Translate (13 mirrors + Lingva fallback), Google Gemini (`google-genai`), OpenAI, DeepSeek, Local LLM (Ollama/LM Studio), DeepL, and LibreTranslate.
- **Modern UI**: Single-window responsive PyQt6 + Qt Quick (QML) dashboard.

**Language:** Python 3.10+ | **GUI:** PyQt6 + QML | **License:** GPL-3.0

---

## 2. Directory Structure

```
UnityLocalizer/
├── run.py                          # Entry point & Qt bootstrap (--self-check verifies runtime dependencies)
├── run.bat / build.bat             # Windows quick launch / build
├── build.py                        # PyInstaller build + frozen --self-check
├── requirements.txt                # Python dependencies
├── AGENTS.md                       # AI orientation & architecture guide
├── README.md                       # User documentation
├── CHANGELOG.md                    # Release changelog
├── LICENSE                         # GNU General Public License v3.0
├── icon.ico / icon.png             # Application branding
├── .github/workflows/ci.yml        # Lint + tests + self-check on Windows, Python 3.10/3.12/3.14
│
├── src/
│   ├── version.py                  # Version info (VERSION = "0.1.0")
│   │
│   ├── core/                       # Core engine & localization pipeline
│   │   ├── engine_profiler.py      # Unity version, Mono/IL2CPP, bitness, platform, frameworks, routes
│   │   ├── hook_layout.py          # BepInEx/XUnity file layout & "runtime really installed" check
│   │   ├── syntax_guard.py         # RichText/format token guard (protected + glossary terms)
│   │   ├── rtl_shaper.py           # Static Arabic/Persian/Hebrew shaping & tag-safe bidi reordering
│   │   ├── languages.py            # 134-language catalog & per-engine language code mapping
│   │   ├── lang_detect/            # Source-language detection (script -> offline py3langid -> Google vote)
│   │   ├── cache.py                # SQLite translation cache (batched get_many/set_many)
│   │   ├── translation_memory.py   # TMX/CSV/TSV/JSON translation memory with fuzzy matching
│   │   ├── glossary.py             # Glossary: terms hidden from engines, replaced in one pass
│   │   ├── constants.py            # Google/Bing endpoints and router limits
│   │   ├── progress.py             # Locale-neutral progress events & cancellation
│   │   │
│   │   ├── harvesters/             # Read-only static text harvesters
│   │   │   ├── text_filter.py        # Shared "is this player-visible text?" rules
│   │   │   ├── metadata_harvester.py # IL2CPP global-metadata.dat string pool extractor
│   │   │   ├── assembly_harvester.py # Mono #US user-string extractor
│   │   │   ├── asset_harvester.py    # UnityPy TextAsset/TextMesh/MonoBehaviour extractor (per-file progress)
│   │   │   ├── typetree_text.py      # Field-aware TypeTree text rules (StringTable, I2, Dialogue System)
│   │   │   ├── typetree_provider.py  # Optional TypeTreeGeneratorAPI loader for stripped player builds
│   │   │   ├── bundle_locator.py     # Discovers scenes, .assets, data.unity3d & Addressables
│   │   │   └── harvest_collector.py  # Aggregates assets, code & StreamingAssets into one pool
│   │   │
│   │   ├── parsers/                # File & framework format parsers
│   │   │   ├── base.py             # BaseParser interface
│   │   │   ├── streaming_assets.py # StreamingAssets (JSON, CSV, TSV, TXT, XML, Yarn, Naninovel, Ink)
│   │   │   ├── auto_translator.py  # XUnity dictionary writer (plain entries + generated regex section)
│   │   │   ├── xunity_codec.py     # Codec mirroring XUnity TextHelper (// comments, %3D, \uXXXX)
│   │   │   ├── xunity_regex.py     # r:"..." entries for runtime-formatted strings ({0}, {name}, %s)
│   │   │   ├── text_formats.py     # Format sniffing & line splitters (JSON, CSV, XML, Yarn)
│   │   │   ├── loc_table.py        # Column-aware string tables (I2 exports, key/source/target columns)
│   │   │   ├── yarn_lines.py       # Yarn line splitter (speaker, body, #line tags, <<commands>>)
│   │   │   ├── ink_json.py         # Compiled Ink (.ink.json) display text extraction & patching
│   │   │   └── naninovel_parser.py # Naninovel .nani text/choices, inline commands preserved
│   │   │
│   │   ├── hook_manager/           # Runtime hooks & font infrastructure
│   │   │   ├── installer.py        # SHA256-pinned BepInEx 5.4.23.5 / 6 (pre.2 or be.764 by metadata) + XUnity 5.6.2
│   │   │   ├── font_bootstrap.py   # AutoTranslatorConfig.ini (offline) & TMP fallback wiring
│   │   │   ├── ini_merge.py        # Line-preserving INI merge (forced keys + missing defaults)
│   │   │   ├── font_provisioner.py # Maps Unity version to prebuilt SDF bundle (5.5-6000)
│   │   │   └── glyph_coverage.py   # Checks deployed characters against the TMP fallback character table
│   │   │
│   │   ├── translators/            # Modular translation subsystem (from RenLocalizer)
│   │   │   ├── base.py             # BaseTranslator, TranslationEngine, TranslationResult
│   │   │   ├── google.py           # Health-aware family routing, separator batches, integrity recovery
│   │   │   ├── google_transport.py # HTTP calls per Google family (POST primary, batchexecute, clients5, Lingva)
│   │   │   ├── bing.py             # Edge keyless Bing: chunking, backoff, size splitting, Google fallback
│   │   │   ├── deepl.py            # DeepL Free/Pro with formality
│   │   │   ├── libretranslate.py   # LibreTranslate (self-hosted or public)
│   │   │   ├── services.py         # Pseudo-localization engine (debug only)
│   │   │   ├── network.py          # NetworkSettings (concurrency, delay, timeout, retries) & ProxyPool
│   │   │   ├── ai_translator.py    # Gemini, OpenAI(-compatible), DeepSeek, Local LLM; fatal-error handling
│   │   │   ├── manager.py          # TranslationManager: cache, memory, glossary, engine factory
│   │   │   └── router.py           # Thread-safe EndpointRouter: IP 429 cooldown, circuit breaker, mirror bans
│   │   │
│   │   └── pipeline/               # Workflow orchestration
│   │       ├── orchestrator.py     # Unified pipeline (Profile -> Harvest -> Translate -> Validate -> Deploy)
│   │       ├── translation_runner.py # Quality-gated parallel batch runner with engine circuit breaker
│   │       ├── review_session.py   # Post-run review rows, guarded manual edits, shippable set
│   │       ├── patch_exporter.py   # Standalone offline patch packager (preflight, payload, config, ZIP)
│   │       └── patch_scripts.py    # Manifest-style install/uninstall .bat scripts & README
│   │
│   ├── backend/                    # PyQt6 QObject bridge layer
│   │   ├── app_backend.py          # Main bridge (signals, slots, background jobs, pipeline outcome)
│   │   ├── editor_backend.py       # Review editor bridge (filter, guarded edits, save to game)
│   │   ├── settings_schema.py      # Typed/clamped schema for every user setting (setSetting)
│   │   └── locale_manager.py       # Dynamic i18n manager for 12 languages
│   │
│   ├── gui/                        # QML interface
│   │   ├── i18n/                   # UI translations (12 languages: tr, en, de, es, fr, ru, pt-BR, ja, zh-CN, ko, it, fa)
│   │   └── qml/
│   │       ├── Main.qml            # Main window & Multi-Theme layout (Obsidian, Daylight, Cyber Neon)
│   │       ├── views/              # DashboardView, ToolboxView, SettingsView, ConsoleView, EditorView, AboutView
│   │       └── components/         # Theme singleton, archetype buttons (Primary/Secondary), NeonSelect, toasts
│   │
│   └── utils/                      # Utilities
│       ├── paths.py                # Resource paths & user data dir (%APPDATA%, .portable)
│       ├── data_migration.py       # One-time copy of legacy data beside the app
│       ├── file_ops.py             # Atomic safe_write, .bak backups, pristine_source()
│       ├── downloader.py           # SHA256-verified cached downloader for runtime dependencies
│       ├── logger.py               # Root logging (rotating app.log) with secret masking
│       ├── self_check.py           # Runtime dependency checks for --self-check
│       └── config.py               # JSON configuration manager
│
└── tests/                          # Test suite (pytest)
```

---

## 3. Core Architecture Rules & Constraints

1. **Language Policy:**
   - Conversations & Architecture discussions: **Turkish**
   - Code symbols, classes, functions, docstrings, technical docs & commit messages: **English**
2. **Single Responsibility Principle (SRP):**
   - Every class and function must have a single clear responsibility. Keep functions under 50 lines.
3. **No Monolithic Files:**
   - Always divide subsystems into logical subpackages (`core`, `harvesters`, `parsers`, `translators`, `backend`, `gui`, `utils`).
4. **Never Leave Placeholders:**
   - No `# TODO: implement later` or `// rest of code`. Always provide complete, functional logic.
5. **Type Hints & Docstrings:**
   - Every function signature must include complete type hints. Use modern typing (`list[str]`, `dict[str, Any]`, `X | None`).
6. **No Silent Error Swallowing:**
   - Never use bare `try-except: pass`. Handle root causes or log exceptions with appropriate severity.
7. **Read-Only UnityPy Rule:**
   - `UnityPy` is strictly for reading and extraction. Never attempt raw `.assets` in-place repacking for modern Unity releases.
8. **Atomic File I/O:**
   - All disk mutations must go through `safe_write` in `src/utils/file_ops.py` with automatic `.bak` creation.

---

## 4. Unity Localization Storage Architecture & Reverse-Engineering Insights

### The 10 Core Text Storage Locations in Unity
1. **Scene & Shared Asset Files (`level*`, `sharedassets*.assets`, `resources.assets`):**
   - **Text Component Types:** `TextMeshProUGUI`, `TextMeshPro`, `UnityEngine.UI.Text`, `ScriptableObject`.
   - **Binary Serialization:** Stored as `MonoBehaviour` (classID 114) with `4-byte Little-Endian length prefix + UTF-8 string + 4-byte padding alignment`.
   - **Coverage:** Represents 70–80% of all UI labels, main menus ("Continue", "Settings", "Gallery", "Credits", "Quit"), HUD, tooltips, and dialogues.
2. **CIL Managed Assemblies (`Managed/Assembly-CSharp.dll`, `*-firstpass.dll`):**
   - **Binary Stream:** String literals stored in the `#US` (User String) stream of .NET PE metadata as UTF-16LE.
   - **Coverage:** Dynamic code strings, format templates, exception messages, code-driven UI text.
3. **IL2CPP String Literal Pool (`il2cpp_data/Metadata/global-metadata.dat`):**
   - **Binary Stream:** Extracted from `StringLiteral` and `StringLiteralData` header definitions.
   - **Coverage:** All compiled C# string literals in AOT builds.
4. **Loose External Files (`StreamingAssets/`):**
   - **File Formats:** Loose `.json`, `.csv`, `.tsv`, `.txt`, `.xml` tables.
5. **I2 Localization Framework (`I2Languages.asset`):**
   - **Structure:** `LanguageSourceData` ScriptableObject holding `mTerms` array of `(Term, TermType, Languages[])`.
   - **Storage:** Found in `resources.assets` or AssetBundles.
6. **Unity Localization Package (`com.unity.localization`):**
   - **Structure:** `StringTableCollection` with `SharedTableData` (KeyIds) and per-locale `StringTable` MonoBehaviour objects.
7. **Visual Novel Engines (Naninovel):**
   - **Structure:** `.nani` script files in `StreamingAssets/Naninovel` or `Resources/Naninovel`.
8. **Narrative & Dialogue Engines (Yarn Spinner, Fungus, Inkle Ink):**
   - **Yarn Spinner:** `.yarn` or compiled `YarnProject` TextAssets.
   - **Fungus:** `Say` and `Menu` blocks serialized in scenes (`level*`).
   - **Ink:** Compiled `.ink.json` TextAssets.
9. **Pixel Crushers Dialogue System for Unity:**
   - **Structure:** `DialogueDatabase` ScriptableObject (conversations, actor names, dialogue entries).
10. **Addressables & Modular AssetBundles (`*.bundle`, `catalog.json`):**
    - Dynamic DLCs and modular asset packages.

### Why Direct Asset Repacking Fails (ZenHax / ResHax Lessons)
- Tools like UABEA attempt in-place bundle re-compression (LZ4/LZMA) which breaks CRC checksums and TypeTree alignments on modern Unity builds (Unity 2020–2023+), leading to game startup crashes.
- **UnityLocalizer's Hybrid Solution:**
  1. **Read-Only Deep Extraction:** Safely dumps strings from `.assets`, `level*`, assemblies, and `StreamingAssets` using `UnityPy` length-prefixed scanner without touching original bundles.
  2. **Zero-Latency In-Memory Redirection:** Loads translated strings into BepInEx + AutoTranslator strictly as an offline dictionary (`Endpoint=`) with zero network lag and zero crash risk.
  3. **UI Layout Collision Protection:** Sets `ForceUIResizing=False` and `EnableUIResizing=True` to prevent translated text from stretching buttons and overlapping neighboring UI elements.

