#!/usr/bin/env bash
# =============================================================================
# RepoPulse Build Script (Linux / macOS)
# =============================================================================
# This script automates the full build pipeline:
#   1. Pre-flight checks  – verify required tools are installed
#   2. Dependency install  – pip install (inside Docker)
#   3. Docker build        – build all containers via Docker Compose
#   4. Validation / tests  – run the test suite inside the container
#   5. Start containers    – launch the application
#
# Usage:
#   chmod +x build.sh
#   ./build.sh              # full build + test + start
#   ./build.sh --skip-tests # build + start, skip tests
#   ./build.sh stop         # stop running containers
#   ./build.sh restart      # stop + full build + test + start
# =============================================================================

set -euo pipefail

# ── Colours (no-op when stdout is not a terminal) ──────────────────────────────
if [ -t 1 ]; then
  GREEN='\033[0;32m'
  RED='\033[0;31m'
  YELLOW='\033[1;33m'
  CYAN='\033[0;36m'
  NC='\033[0m'
else
  GREEN='' RED='' YELLOW='' CYAN='' NC=''
fi

info()    { echo -e "${CYAN}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
fail()    { echo -e "${RED}[FAIL]${NC}  $*"; exit 1; }

# ── Parse arguments ───────────────────────────────────────────────────────────
SKIP_TESTS=false
COMMAND="build"
for arg in "$@"; do
  case "$arg" in
    --skip-tests) SKIP_TESTS=true ;;
    stop)    COMMAND="stop" ;;
    restart) COMMAND="restart" ;;
    -h|--help)
      echo "Usage: ./build.sh [command] [options]"
      echo ""
      echo "Commands:"
      echo "  (default)    Build, test, and start the application"
      echo "  stop         Stop all running containers"
      echo "  restart      Stop containers, rebuild, test, and start"
      echo ""
      echo "Options:"
      echo "  --skip-tests   Build and start without running the test suite"
      echo "  -h, --help     Show this help message"
      exit 0
      ;;
    *)
      warn "Unknown argument: $arg (ignored)"
      ;;
  esac
done

# ── Helper: ensure Docker is available ────────────────────────────────────────
check_docker() {
  command -v docker >/dev/null 2>&1       || fail "docker is not installed. Please install Docker Desktop first."
  docker compose version >/dev/null 2>&1  || fail "docker compose (v2) is not available. Please update Docker Desktop."
  docker info >/dev/null 2>&1             || fail "Docker daemon is not running. Please start Docker Desktop."
}

# ── Command: stop ─────────────────────────────────────────────────────────────
stop_containers() {
  info "Stopping RepoPulse containers …"
  check_docker
  docker compose down
  success "All containers stopped."
}

if [ "$COMMAND" = "stop" ]; then
  stop_containers
  exit 0
fi

if [ "$COMMAND" = "restart" ]; then
  stop_containers
  echo ""
fi

# ── Step 1: Pre-flight checks ────────────────────────────────────────────────
info "Step 1/5 — Checking prerequisites …"

command -v git >/dev/null 2>&1 || fail "git is not installed. Please install git first."
check_docker

success "All prerequisites satisfied."

# ── Step 2: Install dependencies (resolved inside Docker build) ──────────────
info "Step 2/5 — Dependencies will be installed inside the Docker image (requirements.txt)."
if [ ! -f requirements.txt ]; then
  fail "requirements.txt not found in project root."
fi
success "requirements.txt found ($(wc -l < requirements.txt | tr -d ' ') entries)."

# ── Step 3: Build Docker containers ──────────────────────────────────────────
info "Step 3/5 — Building Docker containers …"
docker compose build --no-cache
success "Docker containers built successfully."

# ── Step 4: Run tests ────────────────────────────────────────────────────────
if [ "$SKIP_TESTS" = true ]; then
  warn "Step 4/5 — Tests skipped (--skip-tests flag)."
else
  info "Step 4/5 — Running test suite inside container …"
  docker compose run --rm api python -m pytest tests/ -v
  success "All tests passed."
fi

# ── Step 5: Start containers ─────────────────────────────────────────────────
info "Step 5/5 — Starting RepoPulse containers …"
docker compose up -d
success "Containers started in detached mode."

# ── Done ─────────────────────────────────────────────────────────────────────
echo ""
success "============================================="
success "  RepoPulse build completed successfully! 🚀"
success "============================================="
echo ""
info "API is running at:  http://localhost:8080/"
info "Health check:       http://localhost:8080/health"

info "InfluxDB is running at: http://localhost:8086"
info "Grafana Dashboard: http://localhost:3000"

info "To stop:            ./build.sh stop"
