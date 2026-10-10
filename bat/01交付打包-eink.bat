@echo off
chcp 65001 >nul
:: ---- Block Python bytecode cache: keeps __pycache__ and .pyc out of the synced skill dir ----
::      Python writes engine/__pycache__/*.pyc on every cold import; harmless but noisy in sync.
set "PYTHONDONTWRITEBYTECODE=1"
:: ============================================================
::  eink-deck  GENERIC drag-and-drop DELIVERY PACKAGER (step 2)
::  Usage: drag your [xxx_eink OUTPUT FOLDER] onto this .bat icon.
::
::  This bat lives INSIDE the eink-deck skill folder but is
::  location-independent: copy it to ANY working directory and
::  drag-drop onto it. It locates the packager through the shared
::  skills dir, with an account-junction fallback.
::
::  Two-step workflow:
::    step 1  render  : the 00 render bat  (outline.md -> xxx_eink/index.html)
::    step 2  package : THIS bat (xxx_eink/ -> single-file xxx.html inside)
::
::  What packaging does (see engine/package_deck.py):
::    - inline motion.min.js + lucide.umd.min.js  -> no external file fetch,
::      so stepping animation / B key / WebGL background all work on file://
::    - embed subsetted fonts -> looks identical offline
::      (requires fonttools + font cache; degrades to CDN link with a warning)
::    - output ONE file: <folder-name minus _eink>.html  -> copy THIS single
::      file to ANY computer (no Python, no server needed) and double-click.
::    - safe to re-run: reads index.html fresh each time and overwrites the
::      packaged html; your working draft (index.html + assets) is untouched.
::
::  !! KEEP THIS FILE PURE ASCII + CRLF !!
::    All Chinese messages come from the Python side (UTF-8), never from
::    this bat. Also: NEVER put unescaped ( or ) on an echo line inside a
::    parenthesized if/for block - it closes the block early and kills
::    the bat with "not was unexpected at this time".
:: ============================================================
if "%~1"=="" (
    echo Please drag your [xxx_eink OUTPUT FOLDER] onto this bat icon!
    echo.
    echo Workflow: 1. drag outline.md onto the 00 render bat  2. drag the
    echo resulting xxx_eink folder onto THIS bat to make the delivery file.
    pause
    exit /b
)

if not exist "%~1\index.html" (
    echo ERROR: no index.html inside "%~1".
    echo Drag the OUTPUT FOLDER ending with _eink, not the outline .md file.
    pause
    exit /b
)

:: ---- Locate eink-deck root: prefer this bat's own location, fall back to standard skills dir ----
set "SKILL_DIR=%~dp0.."
if not exist "%SKILL_DIR%\engine\package_deck.py" set "SKILL_DIR=%USERPROFILE%\.workbuddy\skills\eink-deck"

:: Packaging script: eink-deck (truth source)
set "PACKAGE_SCRIPT=%SKILL_DIR%\engine\package_deck.py"

:: ---- Fallback: account-level junction (if the shared dir path differs) ----
if not exist "%PACKAGE_SCRIPT%" set "PACKAGE_SCRIPT=%USERPROFILE%\.workbuddy\skills\eink-deck\engine\package_deck.py"

if not exist "%PACKAGE_SCRIPT%" (
    echo ERROR: package script not found!
    echo Path configured: %PACKAGE_SCRIPT%
    echo Edit this bat and fix SKILL_DIR / PACKAGE_SCRIPT.
    pause
    exit /b
)

where python >nul 2>nul
if errorlevel 1 (
    echo ERROR: python not found. Install Python and enable "Add to PATH".
    pause
    exit /b
)

:: ---- Pick a python that HAS fonttools (needed to embed fonts offline) ----
::      The WorkBuddy-managed python that often sits first on PATH has no
::      fonttools, which silently downgrades the deck to CDN fonts. Probe known
::      installs and use the first one that can import fontTools.
set "PYBIN=python"
set "PYFT="
for %%P in (
    "%USERPROFILE%\AppData\Local\Programs\Python\Python313\python.exe"
    "%USERPROFILE%\AppData\Local\Programs\Python\Python312\python.exe"
    "C:\Program Files\Python\Python313\python.exe"
    "C:\Python313\python.exe"
) do (
    if not defined PYFT (
        if exist "%%~P" (
            "%%~P" -c "import fontTools" >nul 2>nul
            if not errorlevel 1 (
                set "PYBIN=%%~P"
                set "PYFT=1"
            )
        )
    )
)

if defined PYFT (
    echo python [fonttools OK] : %PYBIN%
) else (
    echo NOTE: no python with fonttools found - fonts will NOT be embedded.
    echo       Deck still runs; Chinese fonts fall back to system font OFFLINE.
    echo       Fix once: pip install fonttools brotli into your own python.
)

echo ======================================
echo product folder : %~1
echo script         : %PACKAGE_SCRIPT%
echo ======================================
echo.

"%PYBIN%" "%PACKAGE_SCRIPT%" "%~1"

echo.
if errorlevel 1 (
    echo --------------------------
    echo PACKAGING FAILED - see the error message above.
    pause
    exit /b
)
echo --------------------------
echo Done! The delivery file is INSIDE the folder above.
echo Copy that single .html file anywhere - it runs standalone.
echo Press Enter to open the folder.
pause >nul
explorer "%~1"
