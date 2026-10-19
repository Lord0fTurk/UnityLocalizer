# Global XenForo / BBCode Forum Template — UnityLocalizer

> **Forum Posting Guide:**  
> This template is formatted in universal **XenForo / vBulletin / phpBB BBCode** for major global gaming and modding communities:  
> **CS.RIN.RU, GBAtemp, Romhacking.net, UnknownCheats, Nexus Mods Forums, ResetEra**, etc.  
> In your forum's thread editor, click the **`[ ]` (Toggle BB Code)** button in the toolbar and paste the content below directly.

---

### 🔥 High-Converting Thread Title Suggestions:
1. **[RECOMMENDED - Highest Click-Through Rate]:**  
   `[RELEASE] [OPEN SOURCE] UnityLocalizer: 1-Click 100% Offline Translation & Patching Suite for Unity Games (Solves TextMeshPro "Tofu" □ Boxes!)`
2. **[Feature & Value-Driven]:**  
   `UnityLocalizer v0.1.0 — Ahead-of-Time Game Translation, Auto TMP Fallback Font Injection & Standalone Patch Exporter`
3. **[Problem-Solving / Modding]:**  
   `Tired of In-Game Stutter & Broken Square (□) Glyphs? Translate Any Unity Game Offline with UnityLocalizer`

---

## 📋 Copy-Paste BBCode Content:

[CENTER][B][SIZE=6][COLOR=#00adb5]🎮 UNITYLOCALIZER 🌐[/COLOR][/SIZE][/B]
[SIZE=4][COLOR=#a8a8a8]Autonomous, 100% Offline, Ahead-of-Time Translation & Modding Suite for Unity Engine Games[/COLOR][/SIZE]

[IMG]https://raw.githubusercontent.com/YourUsername/UnityLocalizer/master/icon.png[/IMG]

[B][COLOR=#00e676]Version:[/COLOR][/B] v0.1.0 (Initial Open Source Release) | [B][COLOR=#00e676]License:[/COLOR][/B] GPL-3.0 (100% Free & Open Source)
[URL='https://github.com/YourUsername/UnityLocalizer'][B][COLOR=#ff7675]👉 GitHub Repository & Standalone Windows Download[/COLOR][/B][/URL]
[/CENTER]

[HR][/HR]

[SIZE=5][B]🤔 The Problem We've All Faced...[/B][/SIZE]

You find an amazing indie or mainstream Unity game on Steam, Epic, or itch.io, but it doesn't support your native language. 
When you try conventional real-time on-screen machine translators, you inevitably run into:
[LIST]
[*]Severe [B]gameplay stutter, frame drops, and network latency[/B] while text translates line-by-line during gameplay.
[*]Ugly [B]missing glyph boxes / squares (□ tofu)[/B] because the game's TextMeshPro font doesn't contain characters for your language.
[*]Game-breaking crashes if you attempt dangerous in-place `.assets` bundle repacking (which destroys modern Unity LZ4/LZMA checksums).
[/LIST]

[QUOTE][B]We built [COLOR=#00adb5]UnityLocalizer[/COLOR] to solve all of these problems permanently with an ahead-of-time (AOT) workflow![/B][/QUOTE]

[HR][/HR]

[SIZE=5][B]⚡ What is UnityLocalizer & How Does It Work?[/B][/SIZE]

Following the architecture of its sister tools [I]RenLocalizer[/I] and [I]RPGMLocalizer[/I], **UnityLocalizer** extracts, translates, verifies, and packages your game's text **before you launch the game**. 

Once translated, your game runs **100% offline with zero FPS drop and zero network lag**.

[B]Key Capabilities:[/B]
[LIST]
[*][B]🚀 100% Offline Runtime Playback:[/B] Translates once. In-game, text is served with microsecond lookup speeds via an offline dictionary. No internet connection needed while playing.
[*][B]🔡 TextMeshPro "Tofu" (□) Solution:[/B] Solves missing font glyphs by automatically provisioning a Unity-version-matched ArialUnicode SDF fallback font bundle (Unity 5.5 to 6000) directly to `BepInEx/font/`.
[*][B]🛡️ Safe Read-Only Extraction (Zero Crash Risk):[/B] Safely dumps strings from `.assets`, `level*`, `data.unity3d`, Mono assemblies (`Assembly-CSharp.dll` `#US` stream), IL2CPP `global-metadata.dat`, and loose `StreamingAssets` (JSON, CSV, TSV, XML, TXT, Yarn Spinner, Inkle Ink, Naninovel) using `UnityPy`.
[*][B]🧩 AST Syntax Guard:[/B] Isolates and protects Unity RichText tags (`<color>`, `<size>`, `<sprite>`), NGUI BBCode, and C# formatting tokens (`{0}`, `{playerName}`, `\n`, `%s`). If an engine drops a placeholder, UnityLocalizer automatically repairs word-boundary positioning or flags it for review.
[*][B]🧠 8 Translation Engines Supported:[/B]
[LIST]
[*][B]Free & Keyless:[/B] Multi-mirror Google Translate (13 endpoints with Lingva fallback) and Microsoft Bing (Edge keyless).
[*][B]Professional & APIs:[/B] DeepL (Free & Pro with formality control), LibreTranslate.
[*][B]AI & LLMs:[/B] Google Gemini (`google-genai`), OpenAI (GPT-4o), DeepSeek, and OpenAI-compatible endpoints (OpenRouter).
[*][B]100% Local GPU:[/B] Local LLMs via Ollama & LM Studio for private, offline translation.
[/LIST]
[*][B]🔍 Interactive Review Editor:[/B] Filter, search, and manually edit translated strings with live Syntax Guard validation before pushing to the game.
[*][B]📦 1-Click Standalone Offline Patch Exporter:[/B] Generate a ready-to-share `.zip` patch with bilingual 1-click batch installer & restore scripts (`Install_Patch.bat` / `Uninstall_Patch.bat`). Replaced files are backed up as `.ul_orig` and pristine vanilla state is restored on uninstall!
[*][B]↔️ Full RTL Language Support:[/B] Native static shaping and tag-safe bidirectional reordering for Arabic, Persian, Hebrew, Urdu, Pashto, Sorani, Sindhi, Uyghur, Yiddish, and Dhivehi.
[/LIST]

[HR][/HR]

[SIZE=5][B]🕹️ 3-Step Quickstart Guide[/B][/SIZE]

[B]Step 1: Select Your Game[/B]
Launch UnityLocalizer and select your game's main folder or `.exe`. The built-in profiler immediately detects the Unity version, architecture (Mono vs. IL2CPP, 32-bit vs. 64-bit), and narrative engines.

[B]Step 2: Install Runtime Hook (1-Click)[/B]
Click **"Install Hooks"** on the Dashboard. UnityLocalizer deploys the pinned BepInEx runtime and matches the correct TextMeshPro SDF fallback font bundle automatically.

[B]Step 3: Translate & Play[/B]
Choose your target language and favorite engine, then click **"Start Localization"**. Once finished, launch your game and enjoy playing in your native language!

[QUOTE][B]Useful In-Game Hotkeys:[/B]
[B]ALT + T[/B] : Toggle translation on/off in real-time.
[B]ALT + R[/B] : Reload dictionary files on the fly without restarting the game.[/QUOTE]

[HR][/HR]

[SIZE=5][B]❓ Frequently Asked Questions (FAQ)[/B][/SIZE]

[SPOILER="Which Unity games are compatible?"]
Compatible with almost all Unity 5.x through Unity 6000 games on Windows, both 32-bit and 64-bit, Mono and IL2CPP builds (e.g. Hollow Knight, Subnautica, Cuphead, Sons of the Forest, Phasmophobia, Sunkenland, visual novels, and indie titles).
[/SPOILER]

[SPOILER="Is Linux / Steam Deck supported?"]
[B]Current Status (v0.1.0):[/B] The tool natively targets Windows games (.exe).
[B]Steam Deck / Linux (Proton/Wine):[/B] Yes! Games running via Proton/Wine work great. After patching the game folder on Windows or via Wine, simply add [I]WINEDLLOVERRIDES="winhttp=n,b" %command%[/I] to your Steam game launch options so Proton loads the BepInEx translation proxy.
[B]Roadmap:[/B] Native Linux (.x86_64 / SteamOS) and macOS support are on our active roadmap for v0.2.0 based on community interest!
[/SPOILER]

[SPOILER="What if the game is updated or I want to uninstall?"]
Click "Uninstall Hooks" in the Toolbox, and your game returns to pristine vanilla state immediately. If you installed via an exported patch, just run `Uninstall_Patch.bat` and all `.ul_orig` backups will be restored automatically.
[/SPOILER]

[SPOILER="Do I need a paid API key?"]
No! You can translate completely free using the built-in multi-mirror Google Translate or Microsoft Bing engines. If you have API keys for DeepL, Gemini, or OpenAI, you can configure them in Settings. You can also run Ollama/LM Studio locally on your GPU for free AI translation.
[/SPOILER]

[SPOILER="Will this trigger antivirus false positives?"]
UnityLocalizer is 100% open source under the GPL v3 license. Every line of Python and QML code is publicly inspectable on GitHub. The deployed runtime DLLs are official SHA256-pinned releases of BepInEx and XUnity.AutoTranslator.
[/SPOILER]

[HR][/HR]

[SIZE=5][B]📥 Download & GitHub Repository[/B][/SIZE]

[LIST]
[*][URL='https://github.com/YourUsername/UnityLocalizer/releases'][B][COLOR=#00e676]⬇️ Download Pre-Compiled Windows Release (.ZIP)[/COLOR][/B][/URL]
[*][URL='https://github.com/YourUsername/UnityLocalizer'][B][COLOR=#00adb5]💻 GitHub Repository (Source Code)[/COLOR][/B][/URL]
[/LIST]

[QUOTE][B]For developers running from source:[/B]
[CODE=powershell]git clone https://github.com/YourUsername/UnityLocalizer.git
cd UnityLocalizer
pip install -r requirements.txt
python run.py[/CODE][/QUOTE]

[HR][/HR]

[CENTER]
[B][SIZE=4][COLOR=#ff7675]💬 Feedback & Game Results[/COLOR][/SIZE][/B]
[I]What games have you tested or translated so far? Share your results, questions, or bug reports below! 
If you find the project useful, please consider giving it a [B]Star (⭐)[/B] on GitHub to help others find it![/I]
[/CENTER]
