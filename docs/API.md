# RepoPulse API Guide

The API runs at `http://localhost:8080/api`. All endpoints return JSON.

## Quick Access

- **Interactive API documentation:** http://localhost:8080/docs (Swagger UI)
- **Alternative documentation:** http://localhost:8080/redoc (ReDoc)
- **OpenAPI/Swagger JSON:** http://localhost:8080/openapi.json

No authentication required — all endpoints are public.

---

## Endpoints

### Health & Status

**GET `/health`** — Check if the API is working

**Curl:**
```bash
curl http://localhost:8080/api/health
```

**Response:**
```json
{ "status": "healthy", "service": "RepoPulse API", "version": "1.0.0" }
```

---

**GET `/health/db`** — Check if the database is working

**Curl:**
```bash
curl http://localhost:8080/api/health/db
```

**Response:**
```json
{ "status": "pass", "message": "Connected to InfluxDB" }
```

---

### Jobs (Async Analysis)

Submit a repo to analyze. The job runs in the background.

**POST `/jobs`** — Start a new analysis job

**Parameters:**
- `repo_url` (string, optional) — Public GitHub HTTPS URL (e.g., `https://github.com/owner/repo.git`)
- `local_path` (string, optional) — Absolute path to folder (e.g., `/path/to/repo`)

**Rules:**
- You MUST send one of them, not both
- `repo_url` must be public GitHub HTTPS URL
- `local_path` must be absolute path (starts with `/` or `C:\` on Windows)

**Curl (with GitHub URL):**
```bash
curl -X POST http://localhost:8080/api/jobs \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/owner/repo.git"}'
```

**Curl (with local path):**
```bash
curl -X POST http://localhost:8080/api/jobs \
  -H "Content-Type: application/json" \
  -d '{"local_path": "/absolute/path/to/repo"}'
```

**Response:**
```json
{
  "job_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "status": "queued",
  "created_at": "2026-03-04T10:15:30.123456+00:00"
}
```

**GET `/jobs/{job_id}`** — Get job status and results

**Parameters:**
- `job_id` (string, required) — Job ID from POST /jobs response

**Curl:**
```bash
curl http://localhost:8080/api/jobs/f47ac10b-58cc-4372-a567-0e02b2c3d479
```

**Response:**
```json
{
  "job_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "status": "completed",
  "result": {
    "total_loc": 12450,
    "total_files": 156,
    "total_blank_lines": 2100,
    "total_comment_lines": 1800
  }
}
```

---

**GET `/jobs`** — List all jobs

**Curl:**
```bash
curl http://localhost:8080/api/jobs
```

---

**GET `/workers/health`** — Check worker pool status

**Curl:**
```bash
curl http://localhost:8080/api/workers/health
```

**Response:**
```json
{
  "pool_size": 4,
  "active_workers": 2,
  "queued_jobs": 3,
  "completed_jobs": 47
}
```

---

### Metrics (Direct Analysis)

**POST `/metrics/loc`** — Count lines of code in a folder

**Parameters:**
- `repo_path` (string, required) — Absolute path to folder

**Curl:**
```bash
curl -X POST http://localhost:8080/api/metrics/loc \
  -H "Content-Type: application/json" \
  -d '{"repo_path": "/absolute/path/to/repo"}'
```

Returns a breakdown organized 3 ways: by package, by module, and by file.

**Response (simplified):**
```json
{
  "project_root": "/path/to/repo",
  "total_loc": 12450,
  "total_files": 156,
  "total_blank_lines": 2100,
  "total_comment_lines": 1800,
  "total_weighted_loc": 10500,
  "packages": [
    {
      "package": "com.example.app",
      "loc": 2500,
      "file_count": 25,
      "comment_lines": 400,
      "weighted_loc": 2100,
      "files": [{ "path": "Main.java", "loc": 120, ... }]
    }
  ],
  "modules": [...],
  "files": [...]
}
```

**POST `/analyze`** — Clone a GitHub repo, count lines, measure code changes, and save to database

**Parameters:**
- `repo_url` (string, required) — Public GitHub HTTPS URL
- `start_date` (string, optional) — Start date (format: `YYYY-MM-DD`, defaults to 7 days ago)
- `end_date` (string, optional) — End date (format: `YYYY-MM-DD`, defaults to today)

**Curl:**
```bash
curl -X POST http://localhost:8080/api/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "repo_url": "https://github.com/owner/repo.git",
    "start_date": "2026-02-01",
    "end_date": "2026-03-04"
  }'
```

**Response** — LOC data plus code churn (how many lines were added/deleted):
```json
{
  "repo_url": "https://github.com/owner/repo.git",
  "start_date": "2026-02-01",
  "end_date": "2026-03-04",
  "loc": { "total_loc": 12450, "total_files": 156, ... },
  "churn": { "added": 5200, "deleted": 3100, "modified": 3100, "total": 8300 },
  "churn_daily": {
    "2026-02-01": { "added": 150, "deleted": 80, "modified": 80, "total": 230 },
    "2026-02-02": { "added": 200, "deleted": 120, "modified": 120, "total": 320 }
  }
}
```

**What happens:**
1. Clones the repo (takes time — see timeouts below)
2. Counts all lines of code
3. Counts how many lines were added/deleted in each date
4. Saves metrics to InfluxDB
5. Returns everything

---

## Job Status

Jobs go through these stages:
- `queued` — Waiting to start
- `processing` — Currently running
- `completed` — Done
- `failed` — Error happened

---

## Error Codes & Messages

| Code | Meaning | Example |
|------|---------|----------|
| `200` | Success | Request completed successfully |
| `201` | Created | New job created successfully |
| `400` | Bad request | Missing required parameter or invalid format |
| `404` | Not found | Job ID doesn't exist |
| `422` | Unprocessable entity | repo_path doesn't exist or isn't readable |
| `500` | Server error | Internal API error (check logs) |
| `503` | Service unavailable | InfluxDB is down |

**Example error response:**
```json
{
  "detail": "Job not found: f47ac10b-58cc-4372-a567-0e02b2c3d479"
}
```

---

## Authentication

No authentication is required. All endpoints are publicly accessible.

If you need to restrict access, use a reverse proxy (Nginx, Caddy) in front of the API server.

---

## Timeouts

| Operation | Timeout |
|-----------|----------|
| Clone from GitHub | 120 seconds |
| Analyze repo | Unlimited (job runs in background) |
| Poll for job status | 30 seconds (HTTP timeout) |
| API request | 30 seconds |

If a job takes longer than 120 seconds to clone, use `local_path` instead of `repo_url`.

---

## What the API Counts

The API can count code in these languages:
- Java (.java files)
- Python (.py files)
- TypeScript (.ts files)

For each file, it reports:
- **LOC** — Lines of actual code
- **Blank lines** — Empty lines
- **Comment lines** — Lines that are just comments
- **Weighted LOC** — A score based on code complexity

---

## Postman Collection

To use Postman:

1. **Auto-import from OpenAPI:**
   - Open Postman
   - Click **Import**
   - Paste URL: `http://localhost:8080/openapi.json`
   - Click **Import**
   - All endpoints will be available to test

2. **Manual setup:**
   - Base URL: `http://localhost:8080/api`
   - All endpoints are in **Health & Status**, **Jobs**, and **Metrics** folders
   - No authentication headers required

---
