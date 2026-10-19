# Changelog — UnityLocalizer

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

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
