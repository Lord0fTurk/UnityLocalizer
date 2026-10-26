# -*- coding: utf-8 -*-
"""Windows install/uninstall scripts and README shipped inside an exported patch.

The patch folder mirrors the game folder (``BepInEx/...``, ``<Game>_Data/...``,
proxy DLLs), so it doubles as its own manifest: the installer walks every file
in it, keeps a file it would overwrite as ``<name>.ul_orig`` (or leaves an empty
``<name>.ul_new`` marker when the file is new) and copies the patch file over;
the uninstaller walks the same list and restores each backup or deletes each
marked file. The markers make a second install harmless (the patch's own files
are never mistaken for originals), and a player who already uses BepInEx for
other mods gets their own ``winhttp.dll`` and BepInEx core back on uninstall.

Scripts use subroutines because FOR /R cannot take a FOR variable as its root and
CALL cannot run IF; they are written with CRLF line endings, which cmd.exe needs
to find ``:labels`` reliably.
"""

from __future__ import annotations

from pathlib import Path

from src.core.hook_layout import safe_lang_segment
from src.utils.file_ops import safe_write
from src.version import VERSION

_LANG_TOKEN = "__LANG__"

# Files of the patch itself that are never copied into the game.
PATCH_TOOL_FILES: tuple[str, ...] = (
    "Install_Patch.bat", "Uninstall_Patch.bat", "Yama_Kur.bat", "Yama_Kaldir.bat",
    "Install_Patch.sh", "Uninstall_Patch.sh", "Yama_Kur.sh", "Yama_Kaldir.sh",
    "README.txt", "BENI_OKU.txt",
)

_COMMON_SUBROUTINES = r"""
:no_game
echo [ERROR] No Unity game was found next to this folder.
echo [ERROR] Copy this whole patch folder into the game's main folder
echo [ERROR] (where the game .exe is) and run this script again.
echo.
pause
exit /b 1

:relative
set "SRC=%~1"
setlocal EnableDelayedExpansion
for /F "delims=" %%R in ("!SRC:*%PATCH_ROOT%\=!") do (
    endlocal
    set "REL=%%R"
)
set "DST=%TARGET_DIR%%REL%"
exit /b 0

:is_patch_tool
for %%N in (__TOOLS__) do if /I "%~1"=="%%N" exit /b 0
exit /b 1
"""

_PRELUDE = r"""@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul
set "SCRIPT_DIR=%~dp0"
set "PATCH_ROOT=%SCRIPT_DIR:~0,-1%"
for %%I in ("%SCRIPT_DIR%..") do set "TARGET_DIR=%%~fI\"
set "GAME_FOUND="
for /D %%D in ("%TARGET_DIR%*_Data") do set "GAME_FOUND=1"
"""

_INSTALL_BODY = r"""title UnityLocalizer Offline Patch Installer [__LANG__]
echo =======================================================
echo   UnityLocalizer Standalone Offline Patch Installer
echo   Target Language: __LANG__
echo =======================================================
echo.
if not defined GAME_FOUND goto :no_game

echo [*] Game folder: %TARGET_DIR%
echo [*] Installing the offline translation (replaced files are kept as *.ul_orig)...
for /R "%PATCH_ROOT%" %%F in (*) do call :install_file "%%~fF"

echo.
echo [SUCCESS] Patch installed successfully! 100%% offline.
echo [INFO] You can now start the game normally.
echo.
pause
exit /b 0

:install_file
call :relative "%~1"
call :is_patch_tool "%REL%" && exit /b 0
for %%P in ("%DST%") do if not exist "%%~dpP" mkdir "%%~dpP"
if not exist "%DST%.ul_orig" if not exist "%DST%.ul_new" call :remember_original
copy /Y "%SRC%" "%DST%" >nul
exit /b 0

:remember_original
if exist "%DST%" (
    copy /Y "%DST%" "%DST%.ul_orig" >nul
) else (
    type nul > "%DST%.ul_new"
)
exit /b 0
"""

_UNINSTALL_BODY = r"""title UnityLocalizer Patch Uninstaller
echo =======================================================
echo   UnityLocalizer Patch Uninstaller (Vanilla Restore)
echo =======================================================
echo.
if not defined GAME_FOUND goto :no_game

echo [*] Restoring game files: %TARGET_DIR%
for /R "%PATCH_ROOT%" %%F in (*) do call :remove_file "%%~fF"
for /F "delims=" %%D in ('dir /AD /B /S "%PATCH_ROOT%" 2^>nul ^| sort /R') do call :remove_dir "%%D"

echo.
echo [SUCCESS] Original game files restored. You can delete this patch folder now.
echo.
pause
exit /b 0

:remove_file
call :relative "%~1"
call :is_patch_tool "%REL%" && exit /b 0
if exist "%DST%.ul_orig" (
    move /Y "%DST%.ul_orig" "%DST%" >nul
) else if exist "%DST%.ul_new" (
    del /F /Q "%DST%" "%DST%.ul_new" >nul 2>&1
)
exit /b 0

:remove_dir
call :relative "%~1"
rd "%DST%" 2>nul
exit /b 0
"""

_INSTALL_SH = r"""#!/bin/sh
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PATCH_ROOT="$SCRIPT_DIR"
TARGET_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "======================================================="
echo "  UnityLocalizer Offline Patch Installer [__LANG__]"
echo "======================================================="
echo ""

GAME_FOUND=0
for d in "$TARGET_DIR"/*_Data; do
    if [ -d "$d" ]; then
        GAME_FOUND=1
        break
    fi
done

if [ "$GAME_FOUND" -eq 0 ]; then
    echo "[ERROR] No Unity game was found next to this folder."
    echo "[ERROR] Copy this whole patch folder into the game's main folder"
    echo "[ERROR] (where the game executable is) and run this script again."
    echo ""
    exit 1
fi

echo "[*] Game folder: $TARGET_DIR"
echo "[*] Installing the offline translation (replaced files are kept as *.ul_orig)..."

TOOLS="__TOOLS__"

is_tool() {
    base="$(basename "$1")"
    for t in $TOOLS; do
        if [ "$base" = "$t" ]; then
            return 0
        fi
    done
    return 1
}

# The list goes through a file, not a pipe: a loop at the end of a pipe runs in a subshell, where
# a failing cp would not stop the script and the install would be reported as a success.
LIST="$(mktemp)"
trap 'rm -f "$LIST"' EXIT
find "$PATCH_ROOT" -type f > "$LIST"
FAILED=0
while IFS= read -r src; do
    rel="${src#$PATCH_ROOT/}"
    if is_tool "$rel"; then
        continue
    fi
    dst="$TARGET_DIR/$rel"
    if ! mkdir -p "$(dirname "$dst")"; then
        echo "[ERROR] Could not create the folder for: $rel"
        FAILED=$((FAILED + 1))
        continue
    fi
    if [ ! -f "$dst.ul_orig" ] && [ ! -f "$dst.ul_new" ]; then
        if [ -f "$dst" ]; then
            cp "$dst" "$dst.ul_orig" || { echo "[ERROR] Could not back up: $rel"; FAILED=$((FAILED + 1)); continue; }
        else
            touch "$dst.ul_new" || { echo "[ERROR] Could not prepare: $rel"; FAILED=$((FAILED + 1)); continue; }
        fi
    fi
    cp "$src" "$dst" || { echo "[ERROR] Could not copy: $rel"; FAILED=$((FAILED + 1)); }
done < "$LIST"

if [ "$FAILED" -gt 0 ]; then
    echo ""
    echo "[ERROR] $FAILED file(s) could not be installed. Check the folder permissions and run this script again."
    exit 1
fi

if [ -f "$TARGET_DIR/run_bepinex.sh" ]; then
    chmod +x "$TARGET_DIR/run_bepinex.sh"
    echo ""
    echo "======================================================="
    echo " [INFO] Native Linux game:"
    echo " Start the game through BepInEx. In Steam open Game Properties >"
    echo " Launch Options and add:  ./run_bepinex.sh %command%"
    echo " Without Steam, run ./run_bepinex.sh in the game folder."
    echo "======================================================="
fi

echo ""
echo "[SUCCESS] Patch installed successfully! 100% offline."
echo ""
echo "======================================================="
echo " [INFO] Steam Deck / Linux (Proton) Note:"
echo " If running this Windows game under Proton on Steam,"
echo " open Steam > Game Properties > Launch Options and add:"
echo ' WINEDLLOVERRIDES="winhttp=n,b" %command%'
echo "======================================================="
echo ""
exit 0
"""

_UNINSTALL_SH = r"""#!/bin/sh
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PATCH_ROOT="$SCRIPT_DIR"
TARGET_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "======================================================="
echo "  UnityLocalizer Patch Uninstaller (Vanilla Restore)"
echo "======================================================="
echo ""

GAME_FOUND=0
for d in "$TARGET_DIR"/*_Data; do
    if [ -d "$d" ]; then
        GAME_FOUND=1
        break
    fi
done

if [ "$GAME_FOUND" -eq 0 ]; then
    echo "[ERROR] No Unity game was found next to this folder."
    exit 1
fi

echo "[*] Restoring game files: $TARGET_DIR"

TOOLS="__TOOLS__"

is_tool() {
    base="$(basename "$1")"
    for t in $TOOLS; do
        if [ "$base" = "$t" ]; then
            return 0
        fi
    done
    return 1
}

LIST="$(mktemp)"
trap 'rm -f "$LIST"' EXIT
find "$PATCH_ROOT" -type f > "$LIST"
FAILED=0
while IFS= read -r src; do
    rel="${src#$PATCH_ROOT/}"
    if is_tool "$rel"; then
        continue
    fi
    dst="$TARGET_DIR/$rel"
    if [ -f "$dst.ul_orig" ]; then
        mv -f "$dst.ul_orig" "$dst" || { echo "[ERROR] Could not restore: $rel"; FAILED=$((FAILED + 1)); }
    elif [ -f "$dst.ul_new" ]; then
        rm -f "$dst" "$dst.ul_new" || { echo "[ERROR] Could not remove: $rel"; FAILED=$((FAILED + 1)); }
    fi
done < "$LIST"

if [ "$FAILED" -gt 0 ]; then
    echo ""
    echo "[ERROR] $FAILED file(s) could not be restored. Check the folder permissions and run this script again."
    exit 1
fi

find "$PATCH_ROOT" -depth -type d | while IFS= read -r dir; do
    rel="${dir#$PATCH_ROOT}"
    if [ -n "$rel" ]; then
        rmdir "$TARGET_DIR$rel" 2>/dev/null || true
    fi
done

echo ""
echo "[SUCCESS] Original game files restored. You can delete this patch folder now."
echo ""
exit 0
"""

_README = """=======================================================
  __GAME__ - Offline Patch [__LANG__]
  Powered by UnityLocalizer __VERSION__
=======================================================

[TR] KURULUM TALİMATLARI:
1. ZIP dosyasını oyunun ana klasörüne (oyunun .exe dosyasının yanına) çıkarın;
   içinden çıkan yama klasörü oyun klasörünün içinde durmalıdır.
2. Yama klasöründeki 'Yama_Kur.bat' dosyasına çift tıklayın.
3. Oyunu her zamanki gibi başlatın. Yama tamamen internetsiz (offline) çalışır.
4. Kaldırmak için aynı klasördeki 'Yama_Kaldir.bat' dosyasını çalıştırın; yamanın
   değiştirdiği dosyalar (başka modlarınıza ait olanlar dahil) eski hâline döner.
   Ardından yama klasörünü silebilirsiniz.

[TR] STEAM DECK / LINUX (PROTON) KULLANICILARI:
1. Yama klasörünü oyunun içine kopyalayın.
2. Terminal açıp 'bash Install_Patch.sh' (veya 'bash Yama_Kur.sh') çalıştırın.
3. Steam'de oyuna sağ tıklayıp Özellikler > Başlatma Seçenekleri kutusuna şunu yapıştırın:
   WINEDLLOVERRIDES="winhttp=n,b" %command%
4. Oyunu başlatın!

[EN] INSTALLATION INSTRUCTIONS:
1. Extract the ZIP into the game's main folder (next to the game .exe); the patch
   folder it contains must sit inside the game folder.
2. Double-click 'Install_Patch.bat' inside the patch folder.
3. Launch your game normally. The patch runs 100% offline.
4. To remove it, run 'Uninstall_Patch.bat' from the same folder; every file the
   patch replaced (including files of your other mods) is restored. You can then
   delete the patch folder.

[EN] STEAM DECK / LINUX (PROTON) USERS:
1. Copy the patch folder into the game folder.
2. Open terminal and run 'bash Install_Patch.sh'.
3. In Steam, right-click game > Properties > Launch Options and paste:
   WINEDLLOVERRIDES="winhttp=n,b" %command%
4. Launch the game!
"""


def _crlf(text: str) -> str:
    """Windows line endings for batch and README files."""
    return text.replace("\r\n", "\n").replace("\n", "\r\n")


def _script(body: str, target_lang: str) -> str:
    safe_lang = safe_lang_segment(target_lang).upper()
    common = _COMMON_SUBROUTINES.replace("__TOOLS__", " ".join(PATCH_TOOL_FILES))
    return _crlf(_PRELUDE + body.replace(_LANG_TOKEN, safe_lang) + common)


def _sh_script(body: str, target_lang: str) -> str:
    """Linux shell script with POSIX LF line endings."""
    safe_lang = safe_lang_segment(target_lang).upper()
    tools = " ".join(PATCH_TOOL_FILES)
    return body.replace(_LANG_TOKEN, safe_lang).replace("__TOOLS__", tools).replace("\r\n", "\n")


def write_scripts(patch_dir: Path, target_lang: str) -> None:
    """Write the 1-click install and uninstall scripts (Windows .bat and Linux .sh)."""
    install = _script(_INSTALL_BODY, target_lang)
    uninstall = _script(_UNINSTALL_BODY, target_lang)
    install_sh = _sh_script(_INSTALL_SH, target_lang)
    uninstall_sh = _sh_script(_UNINSTALL_SH, target_lang)
    for name, content in (
        ("Yama_Kur.bat", install), ("Install_Patch.bat", install),
        ("Yama_Kaldir.bat", uninstall), ("Uninstall_Patch.bat", uninstall),
        ("Yama_Kur.sh", install_sh), ("Install_Patch.sh", install_sh),
        ("Yama_Kaldir.sh", uninstall_sh), ("Uninstall_Patch.sh", uninstall_sh),
    ):
        safe_write(patch_dir / name, content, encoding="utf-8", make_backup=False)


def write_readme(patch_dir: Path, game_name: str, target_lang: str) -> None:
    """Write the bilingual README with installation instructions."""
    safe_lang = safe_lang_segment(target_lang).upper()
    content = _crlf(
        _README.replace("__GAME__", game_name).replace(_LANG_TOKEN, safe_lang).replace("__VERSION__", VERSION)
    )
    for name in ("BENI_OKU.txt", "README.txt"):
        safe_write(patch_dir / name, content, encoding="utf-8-sig", make_backup=False)
