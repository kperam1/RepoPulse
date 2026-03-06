# RepoPulse

RepoPulse is a tool that analyzes GitHub repositories and computes software metrics — Lines of Code (LOC), Code Churn, and Work In Progress (WIP). It is built with FastAPI, InfluxDB, and Grafana, all running in Docker containers.

This project was built as part of SER 516 at Arizona State University.

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
   ```

   Check the `.env` file for Grafana and InfluxDB credentials.

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
   - Run the test suite with pytest
   - Start the application in the background

### Build Options

```sh
./build.sh                # full build + test + start
./build.sh --skip-tests   # build + start (skip tests)
./build.sh stop           # stop all containers
./build.sh restart        # stop, rebuild, test, start
```

## How RepoPulse Works

The main entry point is `POST /jobs`. When you submit a job, RepoPulse runs an integrated analysis pipeline in a background worker thread. A single job triggers all of the following steps automatically:

1. **Clone** the repository (shallow clone for speed, or use a local path)
2. **Compute LOC** — scans every supported file (.java, .py, .ts) and counts code lines, comment lines, blank lines, and weighted LOC
3. **Write LOC metrics to InfluxDB** — project-level, package-level, and file-level data points are written in a single batch
4. **Compute Code Churn** — walks the full git history with `git show --numstat` to calculate lines added, deleted, and modified
5. **Compute Daily Churn** — aggregates churn by date
6. **Write Churn metrics to InfluxDB** — both total and daily churn are stored

Once the metrics are in InfluxDB, the time-series query endpoints and the Grafana dashboard read from that data automatically. You do not need to call any other endpoint — the `/jobs` pipeline handles everything end to end.

The standalone endpoints (`POST /metrics/loc`, `POST /analyze`, `POST /metrics/wip`) exist for one-off queries outside the jobs pipeline.

## API Endpoints

The API runs at **http://localhost:8080** once the containers are up. Interactive Swagger docs are available at [http://localhost:8080/docs](http://localhost:8080/docs).

### Core Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Welcome message |
| GET | `/health` | Health check |
| GET | `/health/db` | InfluxDB connection check |
| POST | `/jobs` | Submit a repo analysis job (runs LOC + churn + InfluxDB writes) |
| GET | `/jobs/{job_id}` | Get job status and progress |
| GET | `/jobs/{job_id}/results` | Get structured results (LOC + Churn + metadata) |
| GET | `/workers/health` | Worker pool health (pool size, queue depth, etc.) |

### Standalone Metric Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/metrics/loc` | Compute LOC for a local repo path |
| POST | `/analyze` | Clone a repo, compute LOC + churn, store in InfluxDB |
| POST | `/metrics/wip` | Compute WIP metrics from a Taiga board |

### Time-Series Query Endpoints

These endpoints read from InfluxDB. Data is written there automatically when a job completes.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/metrics/timeseries/snapshots/{repo_id}/latest` | Latest LOC snapshot |
| GET | `/metrics/timeseries/snapshots/{repo_id}/range` | Snapshots in a date range |
| GET | `/metrics/timeseries/snapshots/{repo_id}/at/{timestamp}` | Point-in-time snapshot |
| GET | `/metrics/timeseries/snapshots/{repo_id}/commit/{commit_hash}` | Snapshot for a specific commit |
| GET | `/metrics/timeseries/commits/{repo_id}` | Commits in a date range |
| GET | `/metrics/timeseries/commits/{repo_id}/compare` | Compare two commits |
| GET | `/metrics/timeseries/trend/{repo_id}` | LOC trend over time |
| GET | `/metrics/timeseries/by-branch/{repo_id}` | Latest LOC per branch |
| GET | `/metrics/timeseries/change/{repo_id}` | LOC change between two timestamps |

## Using the Jobs API

`POST /jobs` is the primary way to run analysis. Pass either a `repo_url` (public GitHub URL) or a `local_path` (path to a repo inside the container).

### Submit a job

```sh
curl -s -X POST http://localhost:8080/jobs \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/SimplifyJobs/Summer2026-Internships.git"}' \
  | python3 -m json.tool
```

Or with a local path:

```sh
curl -s -X POST http://localhost:8080/jobs \
  -H "Content-Type: application/json" \
  -d '{"local_path": "/app/src"}' \
  | python3 -m json.tool
```

### Check job status

Use the `job_id` from the response to poll for progress:

```sh
curl -s http://localhost:8080/jobs/<job_id> | python3 -m json.tool
```

### Get structured results

Once the job completes, this returns LOC and churn in a clean format:

```sh
curl -s http://localhost:8080/jobs/<job_id>/results | python3 -m json.tool
```

Example response:

```json
{
  "job_id": "abc-123",
  "status": "completed",
  "metadata": {
    "repository": "https://github.com/owner/repo",
    "analysed_at": "2026-02-27T12:00:00+00:00",
    "scope": "project"
  },
  "loc": {
    "total_loc": 1250,
    "total_files": 15,
    "total_blank_lines": 180,
    "total_excluded_lines": 42,
    "total_comment_lines": 95,
    "total_weighted_loc": 1297.5
  },
  "churn": {
    "added": 142,
    "deleted": 38,
    "modified": 38,
    "total": 180
  }
}
```

| Scenario | Response |
|----------|----------|
| Job completed | Full LOC + churn + metadata |
| Job still running | `{ "status": "processing", "message": "..." }` |
| Job not found | 404 with `{ "detail": "Job not found" }` |

After a job completes, the metrics are in InfluxDB and the Grafana dashboard picks them up automatically.

## Time-Series Metrics

When a job writes LOC data to InfluxDB, it includes the repo ID, commit hash, branch, timestamp, and a full LOC breakdown at project, package, and file granularity. The nine time-series GET endpoints listed above let you query that data in different ways — latest snapshot, date range, trend over time, branch comparison, and so on.

All of this is populated automatically by the jobs pipeline. You do not need to call these endpoints to trigger any computation; they are read-only queries against InfluxDB.

## Code Churn

Code churn measures the volume of change in a codebase over time. RepoPulse computes four values:

| Metric | Definition |
|--------|-----------|
| `added` | Total lines added across all files |
| `deleted` | Total lines removed across all files |
| `modified` | `min(added, deleted)` — lines changed in place |
| `total` | `added + deleted` — overall churn |

How it works:

1. Extracts commit history within the requested date range using `git log`
2. For each commit, runs `git show --numstat --first-parent` to get per-file add/delete counts
3. Skips binary files (reported as `-` in numstat output)
4. Aggregates results into total churn and daily churn (one entry per day)

Churn is computed automatically as part of the `/jobs` pipeline. The `/analyze` endpoint also computes churn as a standalone call.

### Using /analyze directly

```sh
curl -X POST http://localhost:8080/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "repo_url": "https://github.com/SimplifyJobs/Summer2026-Internships.git",
    "start_date": "2025-06-01",
    "end_date": "2025-06-07"
  }'
```

If `start_date` and `end_date` are omitted, they default to the last 7 days.

## WIP Metric (Work In Progress)

WIP tells you how many items are actively being worked on in a Taiga board. For each day it gives three numbers:

| Metric | What it means |
|--------|--------------|
| `wip_count` | Items currently in progress |
| `backlog_count` | Items waiting to be started |
| `done_count` | Items that are finished |

### How it works

RepoPulse uses the Taiga API to pull project data and figure out where each item was on each day:

1. Gets the project info, statuses, and sprints from Taiga
2. For each sprint, retrieves the user stories and their status history
3. Walks through each day in the sprint and checks what status each story had
4. Groups them into backlog (first status column), WIP (in-progress statuses), or done (closed statuses)

For kanban boards, it works the same way but looks at tasks instead of user stories, and uses a date range instead of sprint dates.

### POST /metrics/wip

Send either a `taiga_url` (scrum board) or a `kanban_url` (kanban board). If both are provided, kanban takes priority.

- `taiga_url` — URL of a Taiga scrum board. Returns WIP for user stories per sprint.
- `kanban_url` — URL of a Taiga kanban board. Returns WIP for tasks over a date range.
- `recent_days` (optional) — For scrum: only include sprints from the last N days. For kanban: how many days to look back (default 30).

Scrum example:

```sh
curl -s -X POST http://localhost:8080/metrics/wip \
  -H "Content-Type: application/json" \
  -d '{
    "taiga_url": "https://tree.taiga.io/project/taiga",
    "recent_days": 90
  }' | python3 -m json.tool
```

Kanban example:

```sh
curl -s -X POST http://localhost:8080/metrics/wip \
  -H "Content-Type: application/json" \
  -d '{
    "kanban_url": "https://tree.taiga.io/project/my-kanban-project",
    "recent_days": 30
  }' | python3 -m json.tool
```

| Scenario | Response |
|----------|----------|
| Found sprints or tasks | Daily WIP numbers for each sprint |
| No sprints found | 404 error |
| Bad URL | 400 error |
| Taiga API unreachable | 503 error |

## Weighted LOC

RepoPulse returns both raw LOC and weighted LOC in every response.

### Formula

```
weighted_loc = (code_lines * 1.0) + (comment_lines * 0.5)
```

| Line type | Weight | Reasoning |
|-----------|--------|-----------|
| Code | 1.0 | Executable logic, full complexity weight |
| Comment (pure) | 0.5 | Documentation effort is real but carries less complexity |
| Mixed (code + inline comment) | 1.0 | Contains executable logic, treated as code |
| Blank / excluded | 0.0 | No developer effort |

The 0.5 weight for comments balances between ignoring them entirely and counting them equally with code. Comments represent meaningful effort but do not add executable complexity. Both `loc` and `weighted_loc` are returned at file, package, and project granularity.

## Grafana Dashboard

Grafana is auto-provisioned with the InfluxDB datasource and the RepoPulse Overview dashboard.

- URL: http://localhost:3000
- Username: `admin`
- Password: `admin`

### RepoPulse Overview Dashboard

A unified dashboard that correlates LOC and Code Churn across repositories. It includes:

**Repository summary** — stat panels for total LOC, comment lines, blank lines, and total code churn.

**LOC trend** — LOC over time per repository, plus a stacked breakdown of code, comment, and blank lines.

**Code churn trend** — daily churn as a stacked bar chart (added/deleted/modified), total churn over time as a line chart, and cumulative churn as a running total.

**Churn by file and package** — top 10 most volatile files and packages ranked by LOC change.

**File and package breakdown** — top 10 files and packages by total lines of code.

**Last updated** — timestamps for the most recent LOC and churn data.

The dashboard has a repository dropdown (multi-select) and responds to the Grafana date range selector.

## Worker Pool

`POST /jobs` submits work to a thread pool (default 4 workers). Each worker handles one job at a time: clone, compute LOC, write to InfluxDB, compute churn, write churn to InfluxDB.

```
POST /jobs  ->  queued  ->  processing  ->  completed / failed
```

Check progress with `GET /jobs/{job_id}`. See the whole queue with `GET /jobs`. See pool stats with `GET /workers/health`.

Set `WORKER_POOL_SIZE` in `.env` to change the number of concurrent workers.

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `INFLUX_INIT_TOKEN` | `devtoken12345` | InfluxDB admin token |
| `INFLUX_ORG` | `RepoPulseOrg` | InfluxDB organization |
| `INFLUX_BUCKET` | `repopulse_metrics` | InfluxDB bucket |
| `INFLUX_RETENTION_DAYS` | `90` | Metric retention in days |
| `WORKER_POOL_SIZE` | `4` | Concurrent analysis workers |
| `GF_ADMIN_USER` | `admin` | Grafana admin username |
| `GF_ADMIN_PASSWORD` | `admin` | Grafana admin password |

## Services

| Container | Image | URL | Purpose |
|-----------|-------|-----|---------|
| `repopulse-dev` | local build | http://localhost:8080 | FastAPI backend |
| `repopulse-influx` | `influxdb:2.8` | http://localhost:8086 | Time-series database |
| `repopulse-grafana` | `grafana/grafana:11.5.1` | http://localhost:3000 | Dashboard visualization |

## Project Structure

```
RepoPulse/
  src/
    main.py              # FastAPI entrypoint + worker pool lifecycle
    api/
      models.py          # Pydantic request/response models
      routes.py          # All API endpoints
    core/
      config.py          # Environment variable config
      git_clone.py       # Git clone utility (shallow clone)
      influx.py          # InfluxDB client wrapper + query functions
    metrics/
      loc.py             # LOC counting logic
      churn.py           # Code churn computation
      wip.py             # WIP metrics via Taiga API
    worker/
      pool.py            # Thread-pool worker pool + job queue
      worker.py          # Background metric writer
  tests/                 # Pytest test suite
  monitoring/
    dashboards/          # Grafana dashboard JSON
    provisioning/        # Grafana auto-provisioning configs
  docs/
    API.md               # Detailed API documentation
    DEPLOYMENT.md        # Deployment guide
    PERFORMANCE_BASELINE.md  # Performance benchmarks
  docker-compose.yml
  Dockerfile
  Jenkinsfile            # CI pipeline
  requirements.txt
  build.sh / build.bat
  .env.example
```

## Running Tests Locally

```sh
# Create a virtual environment
python3 -m venv .venv

# Activate it
source .venv/bin/activate          # Unix / macOS
.venv\Scripts\Activate.ps1         # Windows PowerShell
.venv\Scripts\activate             # Windows CMD

# Install dependencies and run tests
pip install -r requirements.txt
pytest
```

To run only the performance benchmarks:

```sh
pytest -m performance -s tests/test_performance.py
```

To run everything except performance tests:

```sh
pytest -m "not performance"
```

Or just use the build script — it runs tests inside Docker automatically.

## Performance Testing

RepoPulse includes automated performance benchmarks (see `tests/test_performance.py`):

- **LOC benchmark**: generates a synthetic repository with 10,000 source files and measures execution time, peak memory, and throughput of `count_loc_in_directory`.
- **Churn benchmark**: creates a git repository with 1,000 commits and measures execution time, peak memory, and throughput of `compute_repo_churn` and `compute_daily_churn`.

Baseline results and threshold details are documented in [docs/PERFORMANCE_BASELINE.md](docs/PERFORMANCE_BASELINE.md).
