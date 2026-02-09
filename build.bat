@echo off
REM =============================================================================
REM RepoPulse Build Script (Windows)
REM =============================================================================
REM This script automates the full build pipeline:
REM   1. Pre-flight checks  - verify required tools are installed
REM   2. Dependency install  - pip install (inside Docker)
REM   3. Docker build        - build all containers via Docker Compose
REM   4. Validation / tests  - run the test suite inside the container
REM   5. Start containers    - launch the application
REM
REM Usage:
REM   build.bat              - full build + test + start
REM   build.bat --skip-tests - build + start, skip tests
REM   build.bat stop         - stop running containers
REM   build.bat restart      - stop + full build + test + start
REM =============================================================================

setlocal enabledelayedexpansion

set "SKIP_TESTS=false"
set "COMMAND=build"

REM ── Parse arguments ─────────────────────────────────────────────────────────
:parse_args
if "%~1"=="" goto :args_done
if /i "%~1"=="--skip-tests" (
    set "SKIP_TESTS=true"
    shift
    goto :parse_args
)
if /i "%~1"=="stop" (
    set "COMMAND=stop"
    shift
    goto :parse_args
)
if /i "%~1"=="restart" (
    set "COMMAND=restart"
    shift
    goto :parse_args
)
if /i "%~1"=="-h" goto :show_help
if /i "%~1"=="--help" goto :show_help
echo [WARN]  Unknown argument: %~1 (ignored)
shift
goto :parse_args

:show_help
echo Usage: build.bat [command] [options]
echo.
echo Commands:
echo   (default)    Build, test, and start the application
echo   stop         Stop all running containers
echo   restart      Stop containers, rebuild, test, and start
echo.
echo Options:
echo   --skip-tests   Build and start without running the test suite
echo   -h, --help     Show this help message
exit /b 0

:args_done

REM ── Command: stop ──────────────────────────────────────────────────────────
if /i "%COMMAND%"=="stop" (
    echo [INFO]  Stopping RepoPulse containers ...
    docker compose down
    if errorlevel 1 (
        echo [FAIL]  Failed to stop containers.
        exit /b 1
    )
    echo [OK]    All containers stopped.
    exit /b 0
)

REM ── Command: restart (stop first, then continue with build) ────────────────
if /i "%COMMAND%"=="restart" (
    echo [INFO]  Stopping RepoPulse containers ...
    docker compose down
    echo [OK]    All containers stopped.
    echo.
)

REM ── Step 1: Pre-flight checks ──────────────────────────────────────────────
echo [INFO]  Step 1/5 - Checking prerequisites ...

where git >nul 2>&1
if errorlevel 1 (
    echo [FAIL]  git is not installed. Please install git first.
    exit /b 1
)

where docker >nul 2>&1
if errorlevel 1 (
    echo [FAIL]  docker is not installed. Please install Docker Desktop first.
    exit /b 1
)

docker compose version >nul 2>&1
if errorlevel 1 (
    echo [FAIL]  docker compose (v2) is not available. Please update Docker Desktop.
    exit /b 1
)

docker info >nul 2>&1
if errorlevel 1 (
    echo [FAIL]  Docker daemon is not running. Please start Docker Desktop.
    exit /b 1
)

echo [OK]    All prerequisites satisfied.

REM ── Step 2: Dependencies (resolved inside Docker build) ────────────────────
echo [INFO]  Step 2/5 - Dependencies will be installed inside the Docker image (requirements.txt).

if not exist requirements.txt (
    echo [FAIL]  requirements.txt not found in project root.
    exit /b 1
)
echo [OK]    requirements.txt found.

REM ── Step 3: Build Docker containers ────────────────────────────────────────
echo [INFO]  Step 3/5 - Building Docker containers ...

docker compose build --no-cache
if errorlevel 1 (
    echo [FAIL]  Docker build failed.
    exit /b 1
)
echo [OK]    Docker containers built successfully.

REM ── Step 4: Run tests ──────────────────────────────────────────────────────
if "%SKIP_TESTS%"=="true" (
    echo [WARN]  Step 4/5 - Tests skipped (--skip-tests flag).
    goto :start_containers
)

echo [INFO]  Step 4/5 - Running test suite inside container ...

docker compose run --rm api python -m pytest tests/ -v
if errorlevel 1 (
    echo [FAIL]  Tests failed.
    exit /b 1
)
echo [OK]    All tests passed.

REM ── Step 5: Start containers ───────────────────────────────────────────────
:start_containers
echo [INFO]  Step 5/5 - Starting RepoPulse containers ...

docker compose up -d
if errorlevel 1 (
    echo [FAIL]  Failed to start containers.
    exit /b 1
)
echo [OK]    Containers started in detached mode.

:build_done
echo.
echo [OK]    =============================================
echo [OK]      RepoPulse build completed successfully!
echo [OK]    =============================================
echo.
echo [INFO]  API is running at:  http://localhost:8080/
echo [INFO]  Health check:       http://localhost:8080/health
echo [INFO]  To stop:            build.bat stop

endlocal
exit /b 0
