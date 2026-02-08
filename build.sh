#!/usr/bin/env bash
set -euo pipefail

# Cross-platform build script (Linux / macOS)
# - Creates a virtual environment at .venv
# - Installs dependencies from requirements.txt
# - Runs tests (pytest)
# - Builds docker images via docker compose (unless NO_DOCKER=1)

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$ROOT_DIR/.venv"
PYTHON_BIN=${PYTHON_BIN:-python3}

echo "[build] root: $ROOT_DIR"
echo "[build] using python: $(command -v "$PYTHON_BIN" 2>/dev/null || true)"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python interpreter '$PYTHON_BIN' not found. Install Python3 or set PYTHON_BIN." >&2
  exit 1
fi

if [ ! -d "$VENV_DIR" ]; then
  echo "[build] creating virtualenv at $VENV_DIR"
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

echo "[build] upgrading pip and installing requirements"
pip install --upgrade pip
pip install -r "$ROOT_DIR/requirements.txt"

echo "[build] running tests"
export PYTHONPATH="$ROOT_DIR"
echo "[build] PYTHONPATH=$PYTHONPATH"
pytest -q

if [ "${NO_DOCKER:-0}" != "1" ]; then
  if command -v docker >/dev/null 2>&1; then
    echo "[build] building docker images (docker compose build)"
    docker compose build
  else
    echo "[build] docker not found; skipping docker build (set NO_DOCKER=1 to silence)"
  fi
else
  echo "[build] NO_DOCKER=1 set; skipping docker build"
fi

echo "[build] SUCCESS: Build completed"
