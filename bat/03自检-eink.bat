@echo off
chcp 65001 >nul
:: ---- Block Python bytecode cache: keeps __pycache__ and .pyc out of the synced skill dir ----
set "PYTHONDONTWRITEBYTECODE=1"
:: ============================================================
::  eink-deck self-check (smoke + golden)
::  Usage: double-click. Runs the two regression gatekeepers
::         against the LIVE skill engine:
::           [1] tests/test_smoke.py   - unit/smoke assertions
::           [2] engine/golden_check.py - lint+render golden gatekeeper
::  Stays PURE ASCII + CRLF (see 00 bat header for why).
::  PYTHON SELECTION: prefer the canonical install that carries the
::  full toolchain (3.13.x). Never trust "where python" alone - PATH
::  order can hand back an Inkscape-bundled 3.12 that lacks fontTools,
::  which would break 02/01 if this same guard were reused there.
::  If the preferred path is missing, fall back to PATH "python" so
::  other machines still run.
::  Locates the engine via the shared skills dir, with an
::  account-junction fallback (same as 00/01/02).
:: ============================================================
set "SKILL_DIR=%~dp0.."
if not exist "%SKILL_DIR%\engine" set "SKILL_DIR=%USERPROFILE%\.workbuddy\skills\eink-deck"
if not exist "%SKILL_DIR%" (
    echo ERROR: eink-deck skill not found.
    echo Checked: %SKILL_DIR%
    echo Fix: make sure the eink-deck skill is reachable via %USERPROFILE%\.workbuddy\skills (junction), or
    echo       make sure C:\Users\^<you^>\.workbuddy\skills points at the shared dir via junction.
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
        "C:\Python313\python.exe"
    ) do ( if not defined PY if exist "%%~P" set "PY=%%~P" )
)
"%PY%" --version
if errorlevel 1 (
    echo ERROR: python not found - tried "%PY%".
    echo        Install Python 3.13 and enable "Add to PATH".
    pause
    exit /b
)
echo ======================================
echo eink-deck self-check
echo skill: %SKILL_DIR%
echo python: %PY%
echo ======================================
echo.
echo [1/2] smoke tests (tests/test_smoke.py)
"%PY%" "%SKILL_DIR%\tests\test_smoke.py"
set "SMOKE_RC=%errorlevel%"
echo.
echo [2/2] golden check (engine/golden_check.py)
"%PY%" "%SKILL_DIR%\engine\golden_check.py"
set "GOLDEN_RC=%errorlevel%"
echo.
echo ======================================
if %SMOKE_RC%==0 if %GOLDEN_RC%==0 (
    echo ALL GREEN - self-check passed.
) else (
    echo SELF-CHECK FAILED - smoke_rc=%SMOKE_RC% golden_rc=%GOLDEN_RC%
)
echo ======================================
pause
