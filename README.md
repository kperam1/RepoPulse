## LOC Metrics Data Model

The LOCMetrics schema is used to represent lines-of-code metrics at project, package, or file granularity. Below are the fields:

| Field         | Type    | Description                                                      |
|-------------- |---------|------------------------------------------------------------------|
| repo_id       | string  | Unique identifier for the repository                             |
| repo_name     | string  | Repository name                                                  |
| branch        | string  | Branch name                                                      |
| commit_hash   | string  | Commit hash                                                      |
| language      | string  | Programming language                                             |
| granularity   | string  | Granularity: 'project', 'package', or 'file'                     |
| project_name  | string? | Project name if applicable                                       |
| package_name  | string? | Package name if applicable                                       |
| file_path     | string? | File path if applicable                                          |
| total_loc     | int     | Total lines of code                                              |
| code_loc      | int     | Lines of code (excluding comments and blanks)                    |
| comment_loc   | int     | Lines of comments                                                |
| blank_loc     | int     | Blank lines                                                      |
| collected_at  | string  | Timestamp when metrics were collected (ISO format)               |

Example (file granularity):

```
{
   "repo_id": "123",
   "repo_name": "example-repo",
   "branch": "main",
   "commit_hash": "abc123",
   "language": "Python",
   "granularity": "file",
   "file_path": "src/main.py",
   "total_loc": 1000,
   "code_loc": 800,
   "comment_loc": 150,
   "blank_loc": 50,
   "collected_at": "2026-02-12T12:00:00Z"
}
```
Prerequisites
Make sure the following are installed on your system:
1. Git
   Used to clone the repository.
   
Check if installed:

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

### Endpoints

| Method | Path             | Description                          |
|--------|------------------|--------------------------------------|
| GET    | `/`              | Welcome message                      |
| GET    | `/health`        | Health check                         |
| POST   | `/jobs`          | Submit a repository analysis job     |
| POST   | `/metrics/loc`   | Compute Lines of Code metrics        |

### LOC Metric (`POST /metrics/loc`)

Compute Lines of Code for a local repository. Supports `.java`, `.py`, and `.ts` files.

**Request:**

```json
{
  "repo_path": "/absolute/path/to/repo"
}
```

**Response:**

```json
{
  "project_root": "/absolute/path/to/repo",
  "total_loc": 42,
  "total_files": 3,
  "total_blank_lines": 8,
  "total_excluded_lines": 6,
  "packages": [
    {
      "package": "src/com/example",
      "loc": 30,
      "file_count": 2,
      "files": [...]
    }
  ],
  "files": [
    {
      "path": "src/com/example/Calculator.java",
      "total_lines": 27,
      "loc": 15,
      "blank_lines": 4,
      "excluded_lines": 8
    }
  ]
}
```

**Exclusion rules:**
- Blank lines (empty or only newline)
- Lines with only whitespace
- Lines with only curly braces `{` or `}`

## Project Structure

```
RepoPulse/
├── src/
│   ├── main.py           # FastAPI app entrypoint
│   ├── api/              # API routes and models
│   ├── core/             # Core config and utilities
│   ├── metrics/          # Metric computation modules
│   │   └── loc.py        # Lines of Code metric
│   └── worker/           # Background worker logic
├── tests/                # Pytest test cases
│   ├── sample_files/     # Sample Java/Python/TS files for testing
│   ├── test_main.py      # API & health check tests
│   └── test_loc.py       # LOC metric tests
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

Running Tests (Local)

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m pytest


## InfluxDB Integration (time-series storage)

This project can write LOC metrics into an InfluxDB v2 instance. The compose setup can include an `influxdb` service and the API/worker are configured to connect to it when the following environment variables are provided.

Create a `.env` file (don't commit real secrets) with values like:

```
INFLUX_INIT_USERNAME=repopulse
INFLUX_INIT_PASSWORD=change_me_locally
INFLUX_ORG=RepoPulseOrg
INFLUX_BUCKET=repopulse_metrics
INFLUX_INIT_TOKEN=devtoken12345
INFLUX_RETENTION_DAYS=90
INFLUX_URL=http://influxdb:8086
INFLUX_TOKEN=devtoken12345
```

How it works:
- If you enable the `influxdb` service in `docker-compose.yml`, the container is initialized with the org, bucket and admin token (for development only).
- The `api` and `worker` services use `INFLUX_URL` and `INFLUX_TOKEN` to connect and write LOC metrics.
- The metrics measurement is `loc_metrics` and fields include `total_loc`, `code_loc`, `comment_loc`, `blank_loc`. Tags include `repo_name`, `repo_id`, `branch`, `language`, and `granularity`.

Health & verification:
- Start the stack: `docker compose up -d influxdb api`
- Visit the Influx UI at `http://localhost:8086` and log in with the init token.
- The API exposes `/health/db` which returns the InfluxDB health status.

Retention and production:
- For production, use Docker secrets for `INFLUX_INIT_TOKEN` / `INFLUX_INIT_PASSWORD` and avoid committing `.env` files.
- Bucket retention is configurable via `INFLUX_RETENTION_DAYS` (defaults to 90 days).

If you want, I can also add an integration pytest that writes and queries a point in the running InfluxDB instance.


