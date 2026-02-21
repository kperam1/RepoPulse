# RepoPulse

A tool that analyzes GitHub repositories and computes Lines of Code (LOC) metrics. Built with FastAPI, InfluxDB, and Grafana — all running in Docker.

## Prerequisites

- [Git](https://git-scm.com/)
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (includes Docker Compose)

## Getting Started

1. Clone the repo and create a `.env` file:
   ```sh
    git clone https://github.com/kperam1/RepoPulse.git
    cd RepoPulse
    # Unix / macOS
    cp .env.example .env
    # Windows PowerShell
    Copy-Item .env.example .env
    # Windows CMD
    copy .env.example .env

    # Refer to .env file for username and password of Grafana and Influx-DB
   ```

2. Build and run:
    ```sh
    # Unix / macOS
    chmod +x build.sh
    ./build.sh
    # Windows (PowerShell or CMD)
    .\build.bat
    ```

3. The build script will:
   - Check that Git and Docker are installed
   - Build all containers
   - Run tests with pytest
   - Start the app in the background

### Build Options

```sh
./build.sh                # full build + test + start
./build.sh --skip-tests   # build + start (skip tests)
./build.sh stop           # stop all containers
./build.sh restart        # stop → rebuild → test → start
```

## API Endpoints

Once running, the API is at **http://localhost:8080**. Interactive docs at [http://localhost:8080/docs](http://localhost:8080/docs).

| Method | Path           | Description                                      |
|--------|----------------|--------------------------------------------------|
| GET    | `/`            | Welcome message                                  |
| GET    | `/health`      | Health check                                     |
| GET    | `/health/db`   | InfluxDB connection check                        |
| POST   | `/jobs`        | Submit a repository analysis job                 |
| POST   | `/metrics/loc` | Compute LOC for a local repo path                |
| POST   | `/analyze`     | **Clone a GitHub repo → compute LOC → store in InfluxDB** |

### Testing the `/analyze` endpoint

This is the main endpoint. Give it a public GitHub URL and it clones the repo, counts lines of code, writes the results to InfluxDB, and returns everything.

**Linux / macOS:**

```sh
curl -X POST http://localhost:8080/analyze \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/SimplifyJobs/Summer2026-Internships.git"}'
```

**Windows PowerShell (recommended):**

```powershell
$body = @{
  repo_url = "https://github.com/SimplifyJobs/Summer2026-Internships.git"
} | ConvertTo-Json

Invoke-RestMethod -Uri http://localhost:8080/analyze -Method POST -ContentType "application/json" -Body $body
```

**Windows CMD:**

```cmd
curl.exe -X POST http://localhost:8080/analyze -H "Content-Type: application/json" -d "{\"repo_url\": \"https://github.com/SimplifyJobs/Summer2026-Internships.git\"}"
```

Example response (trimmed):
```json
{
  "project_root": "/tmp/...",
  "total_loc": 1958,
  "total_files": 3,
  "total_blank_lines": 42,
  "total_excluded_lines": 0,
  "total_comment_lines": 8,
  "packages": ["..."],
  "files": [
    {
      "path": "README.md",
      "total_lines": 1200,
      "loc": 980,
      "blank_lines": 20,
      "excluded_lines": 0,
      "comment_lines": 0
    }
  ]
}
```

After calling `/analyze`, the metrics are stored in InfluxDB and show up on the Grafana dashboard automatically.

## Grafana Dashboard

Grafana is auto-provisioned with the InfluxDB datasource and a LOC metrics dashboard.

- **URL:** http://localhost:3000
- **Username:** `admin`
- **Password:** `admin` 

The dashboard shows:
- Total LOC (stat panel)
- Comment and blank line counts
- LOC by file — top 10 (bar chart)
- LOC by package (bar chart)
- LOC over time (time series)

Key variables:

| Variable               | Default            | Purpose                       |
|------------------------|--------------------|-------------------------------|
| `INFLUX_INIT_TOKEN`   | `devtoken12345`    | InfluxDB admin token          |
| `INFLUX_ORG`          | `RepoPulseOrg`     | InfluxDB organization         |
| `INFLUX_BUCKET`       | `repopulse_metrics`| InfluxDB bucket               |
| `INFLUX_RETENTION_DAYS`| `90`              | Metric retention (days)       |
| `GF_ADMIN_USER`       | `admin`            | Grafana admin username        |
| `GF_ADMIN_PASSWORD`   | `admin`            | Grafana admin password        |

## Project Structure

```
RepoPulse/
├── src/
│   ├── main.py              # FastAPI entrypoint
│   ├── api/
│   │   ├── models.py        # Pydantic request/response models
│   │   └── routes.py        # All API endpoints
│   ├── core/
│   │   ├── config.py        # Environment variable config
│   │   ├── git_clone.py     # Git clone utility (shallow clone)
│   │   └── influx.py        # InfluxDB client wrapper
│   ├── metrics/
│   │   └── loc.py           # LOC counting logic
│   └── worker/
│       └── worker.py        # Background worker
├── tests/                   # Pytest tests
├── monitoring/
│   ├── dashboards/          # Grafana dashboard JSON
│   └── provisioning/        # Grafana auto-provisioning configs
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── build.sh / build.bat
└── .env.example
```

## Running Tests Locally

```sh
# Create venv (Unix/macOS and Windows)
python3 -m venv .venv

# Unix / macOS
source .venv/bin/activate

# Windows PowerShell
.venv\Scripts\Activate.ps1

# Windows CMD
.venv\Scripts\activate

pip install -r requirements.txt
pytest
```

If PowerShell blocks script activation, run:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Or just run `./build.sh` (or `.
build.bat` on Windows) — the build script runs tests inside Docker automatically.

## Services


| Container           | Image                    | URL                      | What it does            |
|---------------------|--------------------------|--------------------------|-------------------------|
| `repopulse-dev`     | local build              | `http://localhost:8080`  | FastAPI backend         |
| `repopulse-influx`  | `influxdb:2.8`           | `http://localhost:8086`  | Time-series DB          |
| `repopulse-grafana` | `grafana/grafana:11.5.1` | `http://localhost:3000`  | Dashboard visualization |
