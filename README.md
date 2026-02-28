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

## Code Churn Metric

Code churn measures the volume of change in a codebase over time. RepoPulse computes four values per commit:

| Metric     | Definition                              |
|------------|-----------------------------------------|
| `added`    | Total lines added across all files      |
| `deleted`  | Total lines deleted across all files    |
| `modified` | `min(added, deleted)` — lines changed in place |
| `total`    | `added + deleted` — overall churn       |

### How RepoPulse computes churn

1. Clones the GitHub repository (full clone to preserve commit history)
2. Extracts commit history within the requested date range using `git log`
3. For each commit, runs `git show --numstat --first-parent` to get per-file add/delete counts
4. Skips binary files (reported as `-` in numstat output)
5. Aggregates results into:
   - **churn** — totals across all commits in the range
   - **churn_daily** — totals grouped by date (one entry per day)

### `/analyze` response

The `/analyze` endpoint now returns both LOC and churn data. The `start_date` and `end_date` fields are optional — if omitted, they default to the last 7 days ending today (UTC).

**With date range (Linux / macOS):**

```sh
curl -X POST http://localhost:8080/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "repo_url": "https://github.com/SimplifyJobs/Summer2026-Internships.git",
    "start_date": "2025-06-01",
    "end_date": "2025-06-07"
  }'
```

**Without dates (defaults to last 7 days):**

```sh
curl -X POST http://localhost:8080/analyze \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/SimplifyJobs/Summer2026-Internships.git"}'
```

**Example response (trimmed):**

```json
{
  "repo_url": "https://github.com/SimplifyJobs/Summer2026-Internships.git",
  "start_date": "2025-06-01",
  "end_date": "2025-06-07",
  "loc": {
    "project_root": "/tmp/...",
    "total_loc": 1958,
    "total_files": 3
  },
  "churn": {
    "added": 142,
    "deleted": 38,
    "modified": 38,
    "total": 180
  },
  "churn_daily": {
    "2025-06-02": {
      "added": 80,
      "deleted": 20,
      "modified": 20,
      "total": 100
    },
    "2025-06-05": {
      "added": 62,
      "deleted": 18,
      "modified": 18,
      "total": 80
    }
  }
}
```

Churn metrics are also written to InfluxDB (`repo_churn` and `repo_churn_daily` measurements).
