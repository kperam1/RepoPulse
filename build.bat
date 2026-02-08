@echo off
REM Cross-platform build script for Windows (cmd)
SETLOCAL ENABLEDELAYEDEXPANSION

if not defined PYTHON (
  where python >nul 2>&1 || (
    echo Python executable not found. Install Python and retry.
    exit /b 1
  )
)

echo [build] creating/activating virtualenv in .venv
python -m venv .venv
call .venv\Scripts\activate

echo [build] upgrading pip and installing requirements
python -m pip install --upgrade pip
pip install -r requirements.txt

echo [build] running tests
SET PYTHONPATH=%CD%
echo [build] PYTHONPATH=%PYTHONPATH%
pytest -q

if "%NO_DOCKER%"=="1" (
  echo [build] NO_DOCKER set; skipping docker build
) else (
  where docker >nul 2>&1 && (
    echo [build] building docker images
    docker compose build
  ) || (
    echo [build] docker not found; skipping docker build
  )
)

echo [build] SUCCESS: Build completed
ENDLOCAL
