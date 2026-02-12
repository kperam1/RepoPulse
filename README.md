
# RepoPulse

## What does RepoPulse do?

- Lets you ask for stats about your GitHub repos
- Runs in Docker, so you don't need to set up a bunch of stuff
- Has Prometheus metrics
- You can change settings with environment variables
- Comes with tests (pytest)

## What do you need?

- [Git](https://git-scm.com/)
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (includes Docker Compose)
- Python 3.8+ and [pip](https://pip.pypa.io/en/stable/) (for development)

## Quick Start — Automated Build (Recommended)

The build scripts do everything for you! They check if you have the right tools, install stuff, build the containers, and run tests. You don't need an IDE.

### Linux / macOS

```sh
git clone https://github.com/kperam1/RepoPulse.git
cd RepoPulse
chmod +x build.sh
./build.sh
```

### Windows

```sh
git clone https://github.com/kperam1/RepoPulse.git
cd RepoPulse
build.bat
```

### Build Script Options

| Command / Flag      | What it does                                 |
|--------------------|----------------------------------------------|
| (no args)          | Full build + test + start the app             |
| stop               | Stop all running containers                   |
| restart            | Stop, rebuild, test, and start                |
| --skip-tests       | Build and start, skip tests                   |
| -h / --help        | Show usage info                              |

#### Examples

```sh
# Linux / macOS
./build.sh                # build, test, and start
./build.sh --skip-tests   # build and start (no tests)
./build.sh stop           # stop the running app
./build.sh restart        # stop → rebuild → test → start

# Windows
build.bat                 REM build, test, and start
build.bat --skip-tests    REM build and start (no tests)
build.bat stop            REM stop the running app
build.bat restart         REM stop → rebuild → test → start
```

### What the build scripts do

- Check if git, docker, and docker compose are installed and Docker is running
- Make sure requirements.txt exists (dependencies are installed inside the Docker image)
- Build all containers from scratch
- Run tests with pytest inside the container (unless you skip tests)
- Start the app in the background

## Manual Steps (if you want)

1. Clone the repository:
   ```sh
   git clone https://github.com/kperam1/RepoPulse.git
   cd RepoPulse
   ```
2. Build the Docker image:
   ```sh
   docker compose build
   ```
3. Run the service:
   ```sh
   docker compose up
   ```
4. Access the API:
   - Open [http://localhost:8080/](http://localhost:8080/) in your browser
   - Or test with curl:
     ```sh
     curl http://localhost:8080/
     ```
5. Stop the service:
   ```sh
   docker compose down
   ```

## API Docs

- Interactive docs: [http://localhost:8080/docs](http://localhost:8080/docs)
- ReDoc: [http://localhost:8080/redoc](http://localhost:8080/redoc)

## Project Structure

```
RepoPulse/
├── src/
│   ├── main.py           # FastAPI app entrypoint
│   ├── api/              # API routes and models
│   ├── core/             # Core config and utilities
│   └── worker/           # Background worker logic
├── tests/                # Pytest test cases
├── requirements.txt      # Python dependencies
├── Dockerfile            # Docker build file
├── docker-compose.yml    # Multi-container setup
└── README.md             # Project documentation
```

## Development

1. Install Python 3.8+ and [pip](https://pip.pypa.io/en/stable/)
2. Install dependencies:
   ```sh
   pip install -r requirements.txt
   ```
3. Run tests:
   ```sh
   pytest
   ```

## Configuration

Edit `src/core/config.py` to change environment variables and settings if you want.


