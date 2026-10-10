@echo off
chcp 65001 >nul
:: ---- Block Python bytecode cache: keeps __pycache__ and .pyc out of the synced skill dir ----
::      Python writes engine/__pycache__/*.pyc on every cold import; harmless but noisy in sync.
set "PYTHONDONTWRITEBYTECODE=1"
:: ============================================================
::  eink-deck  drag-and-drop IMAGE PREP (optional, BEFORE render)
::  Usage: drag an image FILE or a FOLDER onto this .bat icon.
::
::  What it does (see engine/prep_images.py):
::    - shrink long edge to 1920 max, never upscale, never crop content
::    - convert to WebP and shrink file size a lot
::      (measured: PNG 2.9MB -> WebP 336KB, alpha preserved)
::    - write SAME name, SAME folder, NEW .webp extension
::    - ORIGINAL FILES ARE NEVER DELETED
::
::  Why WebP, not JPEG: eink backgrounds are animated WebGL gradients,
::  not a flat color. Transparency should be KEPT so the image blends in.
::  JPEG both loses transparency AND compresses worse than WebP here.
::
::  Flow: dry run first, then you confirm before anything is written.
::  After it finishes, update the outline line it prints, then re-render.
::
::  !! KEEP THIS FILE PURE ASCII + CRLF !!
::    All Chinese messages come from the Python side, never from this
::    bat. Also: NEVER put unescaped ( or ) on an echo line inside a
::    parenthesized if/for block - it closes the block early and kills
::    the bat with "not was unexpected at this time".
:: ============================================================
if "%~1"=="" (
    echo Please drag an IMAGE FILE or a FOLDER onto this bat icon!
    echo.
    echo Examples:
echo   one file : some-photo.png
echo   a folder : images   - every image inside is processed
    echo.
    echo Originals are kept. Output is same name with .webp extension.
    pause
    exit /b
)

:: ---- Locate eink-deck root: prefer this bat's own location, fall back to standard skills dir ----
set "SKILL_DIR=%~dp0.."
if not exist "%SKILL_DIR%\engine\prep_images.py" set "SKILL_DIR=%USERPROFILE%\.workbuddy\skills\eink-deck"

set "PREP_SCRIPT=%SKILL_DIR%\engine\prep_images.py"

:: ---- Fallback: account-level junction (if the shared dir path differs) ----
if not exist "%PREP_SCRIPT%" set "PREP_SCRIPT=%USERPROFILE%\.workbuddy\skills\eink-deck\engine\prep_images.py"

if not exist "%PREP_SCRIPT%" (
    echo ERROR: prep_images.py not found!
    echo Path configured: %PREP_SCRIPT%
    echo Edit this bat and fix SKILL_DIR / PREP_SCRIPT.
    pause
    exit /b
)

where python >nul 2>nul
if errorlevel 1 (
    echo ERROR: python not found. Install Python and enable "Add to PATH".
    pause
    exit /b
)

:: ---- Pick a python that HAS Pillow (required; no silent downgrade) ----
::      The WorkBuddy-managed python that often sits first on PATH has no
::      Pillow. Probe known installs and use the first one that can import it.
set "PYBIN=python"
set "PYPIL="
for %%P in (
    "%USERPROFILE%\AppData\Local\Programs\Python\Python313\python.exe"
    "%USERPROFILE%\AppData\Local\Programs\Python\Python312\python.exe"
    "C:\Program Files\Python\Python313\python.exe"
    "C:\Python313\python.exe"
) do (
    if not defined PYPIL (
        if exist "%%~P" (
            "%%~P" -c "import PIL" >nul 2>nul
            if not errorlevel 1 (
                set "PYBIN=%%~P"
                set "PYPIL=1"
            )
        )
    )
)

if not defined PYPIL (
    echo ERROR: no python with Pillow found on this machine.
    echo        Fix once: pip install Pillow
    echo        Then run this bat again.
    pause
    exit /b
)

echo ======================================
echo target : %~1
echo script : %PREP_SCRIPT%
echo python : %PYBIN%
echo ======================================
echo.
echo STEP 1 of 2 - dry run, nothing is written yet:
echo.

"%PYBIN%" "%PREP_SCRIPT%" "%~1" --dry-run

echo.
echo --------------------------------------
echo STEP 2 of 2 - write the .webp files?
echo   Y = yes, write them - originals are kept, never deleted
echo   N = no, cancel - nothing is written
echo.
set "ANSWER="
set /p ANSWER="Type Y or N, then Enter: "
if /i not "%ANSWER%"=="Y" (
    echo.
    echo Cancelled. Nothing was written.
    pause
    exit /b
)

echo.
"%PYBIN%" "%PREP_SCRIPT%" "%~1"
if errorlevel 1 (
    echo.
    echo --------------------------------------
    echo PREP FAILED - see the error message above.
    echo Nothing was written.
    pause
    exit /b
)

echo.
echo --------------------------------------
echo Done. Originals are still in place.
echo If the report above lists an outline line, update that line to
echo .webp, then re-render and re-package.
echo Press Enter to open the folder.
pause >nul
explorer "%~dp1"
