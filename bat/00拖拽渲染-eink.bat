@echo off
chcp 65001 >nul
:: ---- Block Python bytecode cache: keeps __pycache__ and .pyc out of the synced skill dir ----
::      Python writes engine/__pycache__/*.pyc on every cold import; harmless but noisy in sync.
set "PYTHONDONTWRITEBYTECODE=1"
:: ============================================================
::  eink-deck  GENERIC drag-and-drop renderer (no profile)
::  Usage: drag your [xxx outline.md] file onto this .bat icon.
::
::  This bat lives INSIDE the eink-deck skill folder but is
::  location-independent: copy it to ANY working directory and
::  drag-drop onto it. It locates the engine through the shared
::  skills dir, with an account-junction fallback.
::
::  Two-step workflow:
::    step 1  render  : THIS bat  (outline.md -> xxx_eink/index.html + assets)
::    step 2  package : the 01 delivery bat (xxx_eink folder -> single html)
::
::  Features:
::    - outline lint check runs BEFORE rendering (report only, NEVER blocks).
::    - no profile: theme/fonts come from the outline's own metadata.
::      (Series-specific preset bats pass --profile themselves.)
::
::  !! KEEP THIS FILE PURE ASCII + CRLF !!
::    Non-ASCII bytes + "chcp 65001" make cmd re-seek the file after
::    the codepage switch and chop comment lines into "commands".
::    Also: NEVER put unescaped ( or ) on an echo line inside a
::    parenthesized if/for block - it closes the block early and
::    kills the bat with "not was unexpected at this time".
::    All Chinese messages come from the Python side (UTF-8).
:: ============================================================
if "%~1"=="" (
    echo Please drag your [xxx outline.md] file onto this bat icon!
    echo.
    echo Step 1 render : THIS bat turns outline.md into xxx_eink folder.
    echo Step 2 package: drag the xxx_eink folder onto the 01 bat
    echo to get ONE standalone html for delivery.
    pause
    exit /b
)

set "MD_FILE=%~1"
set "OUT_DIR=%~dpn1_eink"

:: ---- Locate eink-deck root: prefer this bat's own location, fall back to standard skills dir ----
set "SKILL_DIR=%~dp0.."
if not exist "%SKILL_DIR%\engine\render_outline.py" set "SKILL_DIR=%USERPROFILE%\.workbuddy\skills\eink-deck"

:: Render engine: eink-deck (truth source, ships with this skill)
set "RENDER_SCRIPT=%SKILL_DIR%\engine\render_outline.py"

:: ---- Fallback: account-level junction (if the shared dir path differs) ----
if not exist "%RENDER_SCRIPT%" set "RENDER_SCRIPT=%USERPROFILE%\.workbuddy\skills\eink-deck\engine\render_outline.py"

if not exist "%RENDER_SCRIPT%" (
    echo ERROR: render script not found!
    echo Path configured: %RENDER_SCRIPT%
    echo Edit this bat and fix SKILL_DIR / RENDER_SCRIPT.
    pause
    exit /b
)

:: ---- Interpreter: prefer PATH python, fall back to common install locations ----
set "PY=python"
where python >nul 2>nul
if errorlevel 1 (
    set "PY="
    for %%P in (
        "%USERPROFILE%\AppData\Local\Programs\Python\Python313\python.exe"
        "C:\Program Files\Python\Python313\python.exe"
        "%USERPROFILE%\AppData\Local\Programs\Python\Python312\python.exe"
        "C:\Program Files\Python\Python312\python.exe"
    ) do ( if not defined PY if exist "%%~P" set "PY=%%~P" )
)
"%PY%" --version
if errorlevel 1 (
    echo ERROR: python not found - tried "%PY%".
    echo        Install Python 3.13 and enable "Add to PATH".
    pause
    exit /b
)

:: ---- Outline lint (report only, NEVER blocks rendering) ----
set "LINT_SCRIPT=%SKILL_DIR%\engine\lint_outline.py"
if not exist "%LINT_SCRIPT%" set "LINT_SCRIPT=%USERPROFILE%\.workbuddy\skills\eink-deck\engine\lint_outline.py"
if exist "%LINT_SCRIPT%" (
    echo.
    echo [lint] outline guard check - report only, rendering continues regardless...
    "%PY%" "%LINT_SCRIPT%" "%MD_FILE%"
) else (
    echo [lint] lint_outline.py not found - skipping check.
)

echo ======================================
echo outline : %MD_FILE%
echo output  : %OUT_DIR%
echo profile : none - using the outline's own metadata
echo python  : %PY%
echo ======================================

"%PY%" "%RENDER_SCRIPT%" "%MD_FILE%" "%OUT_DIR%"

echo.
if errorlevel 1 (
    echo --------------------------
    echo RENDER FAILED - see the error message above.
    pause
    exit /b
)
echo --------------------------
echo Done! Output folder: %OUT_DIR%
echo Next step: drag the xxx_eink folder onto the 01 delivery bat
echo to get ONE standalone html file.
echo Press Enter to open the output folder.
pause >nul
explorer "%OUT_DIR%"
