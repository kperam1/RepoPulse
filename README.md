# RepoPulse

A metrics and monitoring tool for GitHub repositories.

---

## Prerequisites

Make sure the following are installed on your system:

### 1. Git

Used to clone the repository.

Check if installed:

```bash
git --version
```

If not installed:

- **Mac (Homebrew):** `brew install git`
- **Windows:** Download from [https://git-scm.com/download/win](https://git-scm.com/download/win)
- **Linux:** `sudo apt install git`

### 2. Docker Desktop (includes Docker Compose)

Required to build and run containers.

Check if installed:

```bash
docker --version
docker compose version
```

If not installed:

- **Mac:** [https://docs.docker.com/desktop/install/mac-install/](https://docs.docker.com/desktop/install/mac-install/)
- **Windows:** [https://docs.docker.com/desktop/install/windows-install/](https://docs.docker.com/desktop/install/windows-install/)
- **Linux:** [https://docs.docker.com/desktop/install/linux-install/](https://docs.docker.com/desktop/install/linux-install/)

> After installation, make sure Docker Desktop is **running**.

---

## Quick Start — Automated Build (Recommended)

The automated build scripts handle **everything** — prerequisite checks, dependency installation, Docker container builds, and running the test suite. No IDE required.

### Linux / macOS

```bash
git clone https://github.com/kperam1/RepoPulse.git
cd RepoPulse
chmod +x build.sh
./build.sh
```

### Windows

```cmd
git clone https://github.com/kperam1/RepoPulse.git
cd RepoPulse
build.bat
```

### Build Script Options

| Command / Flag   | Description                                  |
| ---------------- | -------------------------------------------- |
| *(no args)*      | Full build + test + start the application    |
| `stop`           | Stop all running containers                  |
| `restart`        | Stop, rebuild, test, and start               |
| `--skip-tests`   | Build and start, skip tests                  |
| `-h` / `--help`  | Show usage information                       |

**Examples:**

```bash
# Linux / macOS
./build.sh                # build, test, and start
./build.sh --skip-tests   # build and start (no tests)
./build.sh stop           # stop the running app
./build.sh restart        # stop → rebuild → test → start
```

```cmd
REM Windows
build.bat                 REM build, test, and start
build.bat --skip-tests    REM build and start (no tests)
build.bat stop            REM stop the running app
build.bat restart         REM stop → rebuild → test → start
```

### What the build scripts do

1. **Pre-flight checks** — Verify `git`, `docker`, and `docker compose` are installed and the Docker daemon is running.
2. **Dependency validation** — Confirm `requirements.txt` exists (dependencies are installed inside the Docker image automatically).
3. **Docker build** — Run `docker compose build --no-cache` to build all containers from scratch.
4. **Test suite** — Run `pytest` inside the container to validate the build (can be skipped with `--skip-tests`).
5. **Start containers** — Run `docker compose up -d` to launch the application in the background.

---

## Running the Application

The build script automatically starts the containers after a successful build. The API will be available at:

- **Browser:** [http://localhost:8080/](http://localhost:8080/)
- **curl:** `curl http://localhost:8080/`
- **Health check:** `curl http://localhost:8080/health`

Stop the application:

```bash
./build.sh stop       # Linux/Mac
build.bat stop        # Windows
```

---

## Developer Setup (Local Development)

If you want to run the application **outside Docker** for local development and debugging:

### 1. Create a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate        # Linux/Mac
# venv\Scripts\activate         # Windows
```

### 2. Install dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Run the app locally

```bash
uvicorn src.main:app --host 0.0.0.0 --port 8080 --reload
```

### 4. Run tests locally

```bash
python -m pytest tests/ -v
```

---

## Project Structure

```
RepoPulse/
├── build.sh               # Automated build script (Linux/Mac)
├── build.bat              # Automated build script (Windows)
├── docker-compose.yml     # Docker Compose configuration
├── Dockerfile             # Docker image definition
├── requirements.txt       # Python dependencies
├── README.md              # This file
├── src/
│   ├── __init__.py
│   ├── main.py            # FastAPI application entry point
│   ├── api/
│   │   └── routes.py      # API route definitions
│   ├── core/
│   │   └── config.py      # Application configuration
│   └── worker/
│       └── worker.py      # Background worker
└── tests/
    └── test_main.py       # Unit tests
```


