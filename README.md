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

| Method | Path             | Description                                      |
|--------|------------------|--------------------------------------------------|
| GET    | `/`              | Welcome message                                  |
| GET    | `/health`        | Health check                                     |
| GET    | `/health/db`     | InfluxDB connection check                        |
| POST   | `/jobs`          | Submit a repo analysis job (queued to worker pool)|
| GET    | `/jobs/{job_id}` | Get job status and results                       |
| GET    | `/workers/health`| Worker pool health (pool size, queue depth, etc.)|
| POST   | `/metrics/loc`   | Compute LOC for a local repo path                |
| POST   | `/analyze`       | Clone a GitHub repo, compute LOC, store in InfluxDB |
| GET    | `/metrics/timeseries/snapshots/{repo_id}/latest` | Latest snapshot |
| GET    | `/metrics/timeseries/snapshots/{repo_id}/range` | Snapshots in date range |
| GET    | `/metrics/timeseries/snapshots/{repo_id}/at/{timestamp}` | Point-in-time snapshot |
| GET    | `/metrics/timeseries/snapshots/{repo_id}/commit/{commit_hash}` | Snapshots for commit |
| GET    | `/metrics/timeseries/commits/{repo_id}` | Commits in date range |
| GET    | `/metrics/timeseries/commits/{repo_id}/compare` | Compare two commits |
| GET    | `/metrics/timeseries/trend/{repo_id}` | LOC trend over time |
| GET    | `/metrics/timeseries/by-branch/{repo_id}` | Latest LOC per branch |
| GET    | `/metrics/timeseries/change/{repo_id}` | LOC change between timestamps |

### Testing the `/jobs` endpoint

`POST /jobs` is the main way to submit analysis work. Pass either a `repo_url` (public GitHub URL) or a `local_path` (absolute path to a repo already on disk). The job runs in the background via the worker pool.

#### Submit a job with a GitHub URL

**Linux / macOS:**

```sh
curl -s -X POST http://localhost:8080/jobs \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/SimplifyJobs/Summer2026-Internships.git"}' | python3 -m json.tool
```

#### Submit a job with a local path

If the repo is already cloned on the machine running RepoPulse (inside the container), you can pass `local_path` instead:

```sh
curl -s -X POST http://localhost:8080/jobs \
  -H "Content-Type: application/json" \
  -d '{"local_path": "/app/src"}' | python3 -m json.tool
```

#### Check job status and results

Use the `job_id` from the submit response to poll for results:

```sh
curl -s http://localhost:8080/jobs/<job_id> | python3 -m json.tool
```

After a job completes, the metrics are stored in InfluxDB and show up on the Grafana dashboard automatically.

## Time-Series Metrics

Time-series LOC metrics linked to Git commits. See the endpoint table above for all 9 available queries. Data captured: repo, commit hash, branch, timestamp, LOC breakdown, granularity.

### Testing

All 123 unit tests run during `./build.sh` and pass in ~2 seconds (mocked, no InfluxDB needed).

For integration testing, query the running API:
```sh
curl -s "http://localhost:8080/metrics/timeseries/snapshots/test-repo/latest?granularity=project" | python3 -m json.tool
```

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
| `WORKER_POOL_SIZE`    | `4`                | Concurrent analysis workers   |
| `GF_ADMIN_USER`       | `admin`            | Grafana admin username        |
| `GF_ADMIN_PASSWORD`   | `admin`            | Grafana admin password        |

## Worker Pool

POST `/jobs` submits analysis work to a thread-pool (default **4 workers**). Each worker clones the repo, counts LOC, writes metrics to InfluxDB, and stores the result in memory.

```
POST /jobs  →  queued  →  processing  →  completed / failed
```

Check progress with `GET /jobs/{job_id}` or see the whole queue with `GET /jobs`. Use `GET /workers/health` to see pool size, active count, and job totals.

Set `WORKER_POOL_SIZE` in `.env` to change the number of concurrent workers.

## Project Structure

```
RepoPulse/
├── src/
│   ├── main.py              # FastAPI entrypoint + pool lifecycle
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
│       ├── pool.py          # Thread-pool worker pool + job queue
│       └── worker.py        # Background metric writer
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

Or just run `./build.sh` (or `.\build.bat` on Windows) — the build script runs tests inside Docker automatically.

## Weighted LOC — Rationale & Formula

RepoPulse provides both **raw LOC** and **weighted LOC** in every response (file, package, and project level).

### Formula

```
weighted_loc = (code_lines × 1.0) + (comment_lines × 0.5)
```

| Line type | Weight | Rationale |
|-----------|--------|-----------|
| **Code** | 1.0 | Executable logic — full complexity weight |
| **Comment** (pure) | 0.5 | Documentation effort is valuable but carries less executable complexity |
| **Mixed** (code + inline comment) | 1.0 | Treated as code — the line contains executable logic |
| **Blank / excluded** | 0.0 | No developer effort — not counted |

### Why 0.5 for comments?

- Comments represent meaningful developer effort  but do not execute or add cyclomatic complexity.
- A 0.5 multiplier balances between ignoring comments entirely and counting them equally.
- This aligns with industry practices where weighted LOC provides a more accurate picture of a codebase's real "weight" for estimation and comparison.

Both `loc` (raw) and `weighted_loc` are returned in every API response at file, package, and project granularity.

## Services


| Container           | Image                    | URL                      | What it does            |
|---------------------|--------------------------|--------------------------|-------------------------|
| `repopulse-dev`     | local build              | `http://localhost:8080`  | FastAPI backend         |
| `repopulse-influx`  | `influxdb:2.8`           | `http://localhost:8086`  | Time-series DB          |
| `repopulse-grafana` | `grafana/grafana:11.5.1` | `http://localhost:3000`  | Dashboard visualization |
