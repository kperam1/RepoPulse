@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM =============================================================================
REM RepoPulse Build Script (Windows)
REM =============================================================================
REM This script automates the full build pipeline:
REM   1. Pre-flight checks  - verify required tools are installed
REM   2. Dependency install - pip install (inside Docker)
REM   3. Docker build       - build all containers via Docker Compose
REM   4. Validation/tests   - run the test suite inside the container
REM   5. Start containers   - launch the application
REM
REM Usage:
REM   build.bat              - full build + test + start
REM   build.bat --skip-tests - build + start, skip tests
REM   build.bat stop         - stop running containers
REM   build.bat restart      - stop + full build + test + start
REM =============================================================================

set "SKIP_TESTS=false"
set "COMMAND=build"

REM ── Parse arguments ─────────────────────────────────────────────────────────
:parse_args
if "%~1"=="" goto :args_done
if /i "%~1"=="--skip-tests" (set "SKIP_TESTS=true" & shift & goto :parse_args)
if /i "%~1"=="stop" (set "COMMAND=stop" & shift & goto :parse_args)
if /i "%~1"=="restart" (set "COMMAND=restart" & shift & goto :parse_args)
if /i "%~1"=="-h" goto :show_help
if /i "%~1"=="--help" goto :show_help
echo [WARN] Unknown argument: %~1
shift
goto :parse_args

:show_help
echo Usage: build.bat [stop^|restart] [--skip-tests]
exit /b 0

:args_done

REM ── Ensure script runs from project root ───────────────────────────────────
cd /d "%~dp0"

REM ── Detect docker compose command ──────────────────────────────────────────
docker compose version >nul 2>&1
if %errorlevel%==0 (
    set "DC=docker compose"
) else (
    docker-compose version >nul 2>&1
    if %errorlevel%==0 (
        set "DC=docker-compose"
    ) else (
        echo [FAIL] Docker Compose not found.
        exit /b 1
    )
)

REM ── STOP COMMAND ───────────────────────────────────────────────────────────
if /i "%COMMAND%"=="stop" (
    echo [INFO] Stopping containers...
    %DC% down
    exit /b 0
)

REM ── RESTART COMMAND ────────────────────────────────────────────────────────
if /i "%COMMAND%"=="restart" (
    echo [INFO] Restarting containers...
    %DC% down
)

REM ── Step 1: Checks ─────────────────────────────────────────────────────────
echo [INFO] Checking prerequisites...

where git >nul 2>&1 || (echo [FAIL] Git not installed & exit /b 1)
where docker >nul 2>&1 || (echo [FAIL] Docker not installed & exit /b 1)

docker info >nul 2>&1
if errorlevel 1 (
    echo [FAIL] Docker Desktop is not running.
    exit /b 1
)

echo [OK] Prerequisites satisfied.

REM ── Step 2: requirements.txt ───────────────────────────────────────────────
if not exist requirements.txt (
    echo [FAIL] requirements.txt missing.
    exit /b 1
)

REM ── Step 3: Build ──────────────────────────────────────────────────────────
echo [INFO] Building containers...
%DC% build
if errorlevel 1 exit /b 1

REM ── Step 4: Tests ──────────────────────────────────────────────────────────
if "%SKIP_TESTS%"=="true" goto :start

echo [INFO] Running tests...
%DC% run --rm api pytest -v
if errorlevel 1 (
    echo [FAIL] Tests failed.
    exit /b 1
)

REM ── Step 5: Start ──────────────────────────────────────────────────────────
:start
echo [INFO] Starting containers...
%DC% up -d
if errorlevel 1 exit /b 1

echo.
echo ======================================
echo RepoPulse is running 🚀
echo API: http://localhost:8080
echo Health: http://localhost:8080/health
echo Influx-DB: http://localhost:8086
echo Grafana Dashboard: http://localhost:3000
echo ======================================

endlocal
exit /b 0
