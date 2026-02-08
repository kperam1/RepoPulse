Prerequisites
Make sure the following are installed on your system:
1. Git
   Used to clone the repository.
   
Check if installed:

git --version

If not installed:

Mac (Homebrew):

brew install git

Windows:

Download from: https://git-scm.com/download/win

Linux:

sudo apt install git

2. Docker Desktop (includes Docker Compose)
   
Required to build and run containers.

Check if installed:

docker --version

docker compose version

If not installed:

Mac:
https://docs.docker.com/desktop/install/mac-install/

Windows:
https://docs.docker.com/desktop/install/windows-install/

Linux:
https://docs.docker.com/desktop/install/linux-install/

After installation, make sure Docker Desktop is running.

Clone the Repository

git clone https://github.com/kperam1/RepoPulse.git

cd RepoPulse

Build the Project

docker compose build

Run the Project

docker compose up

Access the API

Open in browser:

http://localhost:8080/

Or test using curl:

curl http://localhost:8080/

Stop the Project

docker compose down


Automated build scripts
-----------------------

This repository includes cross-platform build scripts that automate environment setup, validation, and Docker image builds.

Linux / macOS

Run the shell build script from the repository root:

```bash
./build.sh
```

Behavior:
- Creates a virtual environment at `.venv` using the system Python (or the interpreter in $PYTHON_BIN).
- Installs Python dependencies from `requirements.txt`.
- Runs the test suite with `pytest` (validation step). If tests fail the build exits with non-zero status.
- Builds Docker images with `docker compose build` unless the environment variable `NO_DOCKER=1` is set.

Windows (cmd)

Run the batch build script from the repository root:

```cmd
build.bat
```

Behavior is the same as the shell script (creates `.venv`, installs dependencies, runs tests, builds Docker).

Developer setup vs build
- The build scripts aim to produce a reproducible, automated build for CI or local use.
- For iterative local development you can still use the Docker-based instructions above or create/activate the virtualenv manually:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn src.main:app --reload
```

If you prefer Docker-only development, run:

```bash
docker compose up --build
```

Notes
- If you don't want Docker builds during the automated build, set `NO_DOCKER=1`.
- The build scripts assume Python 3.x is available on PATH.


