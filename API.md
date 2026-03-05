# RepoPulse API Guide

The API runs at `http://localhost:8080/api`. All endpoints return JSON.

---

## Endpoints

### Health & Status

**GET `/health`** — Check if the API is working
```json
{ "status": "healthy", "service": "RepoPulse API", "version": "1.0.0" }
```

**GET `/health/db`** — Check if the database is working
```json
{ "status": "pass", "message": "Connected to InfluxDB" }
```

---

### Jobs (Async Analysis)

Submit a repo to analyze. The job runs in the background.

**POST `/jobs`** — Start a new analysis job

Send either `repo_url` (GitHub link) or `local_path` (folder on disk), but not both:
```json
{ "repo_url": "https://github.com/owner/repo.git" }
```

Or:
```json
{ "local_path": "/absolute/path/to/repo" }
```

**Rules:**
- `repo_url` must be a public GitHub HTTPS URL (format: `https://github.com/owner/repo` or `https://github.com/owner/repo.git`)
- `local_path` must be an absolute path (starts with `/` or `C:\` on Windows)
- You MUST send one of them, not both

Response:
```json
{
  "job_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "status": "queued",
  "created_at": "2026-03-04T10:15:30.123456+00:00"
}
```

**GET `/jobs/{job_id}`** — Get job status and results
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

**GET `/jobs`** — List all jobs

**GET `/workers/health`** — How many workers are running and how many jobs are waiting
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
```json
{ "repo_path": "/absolute/path/to/repo" }
```

Returns a breakdown organized 3 ways: by package, by module, and by file.

**Example response (simplified):**
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

**Required:**
- `repo_url` — Public GitHub HTTPS URL

**Optional:**
- `start_date` — When to start counting changes (format: `YYYY-MM-DD`, defaults to 7 days ago)
- `end_date` — When to stop counting changes (format: `YYYY-MM-DD`, defaults to today)

```json
{
  "repo_url": "https://github.com/owner/repo.git",
  "start_date": "2026-02-01",
  "end_date": "2026-03-04"
}
```

Returns LOC data plus code churn (how many lines were added/deleted):
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

## Error Codes

- `200` — Success
- `201` — Job created
- `400` — Bad request (wrong data sent)
- `404` — Not found (job doesn't exist)
- `500` — Server error
- `503` — Service is down

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
