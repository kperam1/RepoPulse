import time
import logging
from datetime import datetime

from src.core.influx import write_loc_metric

logger = logging.getLogger("repopulse.worker")


def run_worker():
    """Example worker loop that writes a sample LOC metric to InfluxDB every 5s.

    Replace the payload construction with your real metric collection logic.
    """
    while True:
        payload = {
            "repo_id": "local-000",
            "repo_name": "local-repo",
            "branch": "main",
            "language": "python",
            "granularity": "project",
            "project_name": "example_project",
            "package_name": None,
            "file_path": None,
            "total_loc": 123,
            "code_loc": 100,
            "comment_loc": 15,
            "blank_loc": 8,
            "collected_at": datetime.utcnow().isoformat() + "Z",
        }

        try:
            write_loc_metric(payload)
            logger.info("Wrote sample LOC metric to InfluxDB")
        except Exception as e:
            logger.warning("Failed to write LOC metric: %s", e)

        time.sleep(5)


if __name__ == "__main__":
    run_worker()