<h1 align="center">RepoPulse</h1>

<p align="center">
<b>Metrics and monitoring tool for GitHub repositories</b><br>
<i>FastAPI-based API for repository analytics, health, and insights</i>
</p>

---

## Overview

RepoPulse is a containerized API service that provides metrics, monitoring, and analytics for GitHub repositories. Built with FastAPI, it enables users to query repository health, activity, and other insights programmatically or via browser.

## Features

- Exposes RESTful API endpoints for repository metrics
- Containerized with Docker for easy deployment
- Prometheus metrics integration
- Configurable via environment variables
- Includes automated tests with pytest

## Requirements

- [Git](https://git-scm.com/)
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (includes Docker Compose)

## Quick Start

1. **Clone the repository:**
   ```sh
   git clone https://github.com/kperam1/RepoPulse.git
   cd RepoPulse
   ```

2. **Build the Docker image:**
   ```sh
   docker compose build
   ```

3. **Run the service:**
   ```sh
   docker compose up
   ```

4. **Access the API:**
   - Open [http://localhost:8080/](http://localhost:8080/) in your browser
   - Or test with curl:
     ```sh
     curl http://localhost:8080/
     ```

5. **Stop the service:**
   ```sh
   docker compose down
   ```

## API Documentation

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

Edit `src/core/config.py` to adjust environment variables and settings as needed.


