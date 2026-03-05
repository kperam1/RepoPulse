import logging
import requests
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Dict, List

logger = logging.getLogger("repopulse.metrics.wip")

TAIGA_API_BASE = "https://api.taiga.io/api/v1"


class TaigaFetchError(Exception):
    """Raised when Taiga API calls fail."""
    pass


@dataclass
class DailyWIPMetric:
    """Represents WIP for a single day."""
    date: str  # ISO format: YYYY-MM-DD
    wip_count: int
    backlog_count: int
    done_count: int


@dataclass
class WIPMetric:
    """Represents the WIP metric time-series for a Taiga project."""
    project_id: Optional[int] = None
    project_slug: Optional[str] = None
    sprint_id: Optional[int] = None
    sprint_name: Optional[str] = None
    date_range_start: Optional[str] = None
    date_range_end: Optional[str] = None
    daily_wip: List[DailyWIPMetric] = field(default_factory=list)


def _validate_taiga_url(taiga_url: str) -> str:
    if not taiga_url:
        raise ValueError("Taiga URL cannot be empty")
    
    taiga_url = taiga_url.strip().rstrip("/")
    
    if "/project/" not in taiga_url:
        raise ValueError("Invalid Taiga URL. Expected format: https://taiga.io/project/{slug}")
    
    parts = taiga_url.split("/project/")
    if len(parts) != 2 or not parts[1]:
        raise ValueError("Could not extract project slug from URL")
    
    return parts[1]


def _get_project_id(project_slug: str) -> int:
    try:
        logger.debug(f"Fetching project ID for slug: {project_slug}")
        resp = requests.get(
            f"{TAIGA_API_BASE}/projects/by_slug",
            params={"slug": project_slug},
            timeout=10,
        )
        resp.raise_for_status()

        project = resp.json()
        if not project or not isinstance(project, dict):
            raise TaigaFetchError(f"No project found with slug: {project_slug}")

        project_id = project.get("id")
        if not project_id:
            raise TaigaFetchError(f"Project {project_slug} returned no ID in API response")

        logger.debug(f"Found project ID {project_id} for slug {project_slug}")
        return project_id

    except requests.RequestException as e:
        raise TaigaFetchError(f"Failed to fetch project '{project_slug}': {e}")
    except (KeyError, TypeError) as e:
        raise TaigaFetchError(f"Unexpected API response: {e}")


def _get_project_statuses(project_id: int) -> Dict[int, dict]:
    try:
        logger.debug(f"Fetching statuses for project {project_id}")
        resp = requests.get(
            f"{TAIGA_API_BASE}/userstory-statuses",
            params={"project": project_id},
            timeout=10,
        )
        resp.raise_for_status()

        statuses = resp.json()
        if not statuses:
            raise TaigaFetchError(f"No statuses found for project {project_id}")

        status_map = {
            s.get("id"): {
                "name": s.get("name", "Unknown"),
                "is_closed": s.get("is_closed", False),
                "order": s.get("order", 999),
            }
            for s in statuses
        }
        logger.debug(f"Found {len(status_map)} statuses")
        return status_map

    except requests.RequestException as e:
        raise TaigaFetchError(f"Failed to fetch statuses: {e}")
    except (KeyError, TypeError) as e:
        raise TaigaFetchError(f"Unexpected API response: {e}")


def _get_userstories(project_id: int) -> List[dict]:
    try:
        logger.debug(f"Fetching userstories for project {project_id}")
        resp = requests.get(
            f"{TAIGA_API_BASE}/userstories",
            params={"project": project_id},
            timeout=10,
        )
        resp.raise_for_status()

        stories = resp.json()
        logger.debug(f"Found {len(stories)} stories")
        return stories if isinstance(stories, list) else []

    except requests.RequestException as e:
        raise TaigaFetchError(f"Failed to fetch userstories: {e}")
    except TypeError as e:
        raise TaigaFetchError(f"Unexpected API response: {e}")


def _get_userstory_history(userstory_id: int) -> List[dict]:
    try:
        logger.debug(f"Fetching history for userstory {userstory_id}")
        resp = requests.get(
            f"{TAIGA_API_BASE}/history/userstory/{userstory_id}",
            timeout=10,
        )
        resp.raise_for_status()

        events = resp.json()
        logger.debug(f"Found {len(events) if isinstance(events, list) else 0} history events")
        return events if isinstance(events, list) else []

    except requests.RequestException as e:
        logger.warning(f"Failed to fetch history for userstory {userstory_id}: {e}")
        return []
    except TypeError as e:
        logger.warning(f"Unexpected API response for history: {e}")
        return []


def _get_sprint_dates(project_id: int, sprint_id: int) -> tuple[datetime, datetime]:
    try:
        logger.debug(f"Fetching milestone {sprint_id} for project {project_id}")
        resp = requests.get(
            f"{TAIGA_API_BASE}/milestones/{sprint_id}",
            params={"project": project_id},
            timeout=10,
        )
        resp.raise_for_status()

        milestone = resp.json()
        start_str = milestone.get("estimated_start")
        end_str = milestone.get("estimated_finish")

        if not start_str or not end_str:
            raise TaigaFetchError(f"Sprint {sprint_id} missing date fields")

        start = datetime.fromisoformat(start_str.replace("Z", "+00:00")).date()
        end = datetime.fromisoformat(end_str.replace("Z", "+00:00")).date()

        logger.debug(f"Sprint range: {start} → {end}")
        return start, end

    except requests.RequestException as e:
        raise TaigaFetchError(f"Failed to fetch sprint dates: {e}")
    except (KeyError, ValueError) as e:
        raise TaigaFetchError(f"Invalid sprint date format: {e}")


def _extract_status_at_date(history_events: List[dict], target_date: datetime) -> Optional[int]:
    target_datetime = datetime.combine(target_date, datetime.max.time())

    status_at_date = None

    for event in sorted(history_events, key=lambda e: e.get("created_at", "")):
        try:
            created_str = event.get("created_at", "")
            if not created_str:
                continue

            event_dt = datetime.fromisoformat(created_str.replace("Z", "+00:00"))

            if event_dt.date() <= target_date:
                values_diff = event.get("values_diff", {})
                if "status" in values_diff:
                    status_change = values_diff["status"]
                    if isinstance(status_change, (list, tuple)) and len(status_change) >= 3:
                        status_at_date = status_change[2]
        except (KeyError, ValueError, TypeError):
            continue

    return status_at_date


def _categorize_status(
    status_id: Optional[int],
    status_map: Dict[int, dict],
    min_order: Optional[int] = None,
) -> str:
    if status_id is None:
        return "backlog"

    status_info = status_map.get(status_id, {})
    if status_info.get("is_closed", False):
        return "backlog"

    if min_order is None:
        min_order = min((s.get("order", 999) for s in status_map.values()), default=999)
    current_order = status_info.get("order", 999)

    if current_order == min_order:
        return "backlog"

    return "wip"


def _get_milestones(project_id: int) -> List[dict]:
    try:
        logger.debug(f"Fetching milestones for project {project_id}")
        resp = requests.get(
            f"{TAIGA_API_BASE}/milestones",
            params={"project": project_id},
            timeout=10,
        )
        resp.raise_for_status()

        data = resp.json()
        # Taiga API returns paginated results with "results" key
        if isinstance(data, dict) and "results" in data:
            milestones = data["results"]
        elif isinstance(data, list):
            milestones = data
        else:
            milestones = []
        return milestones

    except requests.RequestException as e:
        raise TaigaFetchError(f"Failed to fetch milestones: {e}")
    except TypeError as e:
        raise TaigaFetchError(f"Unexpected API response: {e}")


def calculate_daily_wip(
    taiga_url: str,
    sprint_id: int,
) -> WIPMetric:
    logger.info(f"Calculating daily WIP for: {taiga_url}, sprint_id={sprint_id}")

    try:
        slug = _validate_taiga_url(taiga_url)
        project_id = _get_project_id(slug)
        sprint_start, sprint_end = _get_sprint_dates(project_id, sprint_id)
        status_map = _get_project_statuses(project_id)
        min_order = min((s.get("order", 999) for s in status_map.values()), default=999)
        stories = _get_userstories(project_id)
        story_map: Dict[int, dict] = {s.get("id"): s for s in stories if s.get("id")}
        story_histories: Dict[int, List[dict]] = {}
        for sid in story_map.keys():
            story_histories[sid] = _get_userstory_history(sid)
        daily_results: List[DailyWIPMetric] = []
        current_date = sprint_start
        while current_date <= sprint_end:
            wip_count = 0
            backlog_count = 0
            done_count = 0
            for story_id, history in story_histories.items():
                status_at_date = _extract_status_at_date(history, current_date)
                if status_at_date is None:
                    story = story_map.get(story_id, {})
                    created_str = story.get("created_date")
                    if created_str:
                        try:
                            created_date = datetime.fromisoformat(created_str.replace("Z", "+00:00")).date()
                        except Exception:
                            created_date = None
                        if created_date and current_date < created_date:
                            status_at_date = None
                        else:
                            status_at_date = story.get("status")
                    else:
                        status_at_date = story.get("status")
                category = _categorize_status(status_at_date, status_map, min_order)

                if category == "wip":
                    wip_count += 1
                elif category == "backlog":
                    backlog_count += 1
                elif category == "done":
                    done_count += 1

            daily_results.append(
                DailyWIPMetric(
                    date=current_date.isoformat(),
                    wip_count=wip_count,
                    backlog_count=backlog_count,
                    done_count=done_count,
                )
            )

            current_date += timedelta(days=1)

        metric = WIPMetric(
            project_id=project_id,
            project_slug=slug,
            sprint_id=sprint_id,
            date_range_start=sprint_start.isoformat(),
            date_range_end=sprint_end.isoformat(),
            daily_wip=daily_results,
        )

        logger.info(f"Daily WIP calculated: {len(daily_results)} days")
        return metric

    except (ValueError, TaigaFetchError) as e:
        logger.error(f"Failed to calculate daily WIP: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise TaigaFetchError(f"Unexpected error: {e}")


def calculate_daily_wip_all_sprints(
    taiga_url: str,
    recent_days: Optional[int] = None,
) -> List[WIPMetric]:
    logger.info(f"Calculating daily WIP for all sprints: {taiga_url} (recent_days={recent_days})")

    try:
        slug = _validate_taiga_url(taiga_url)
        project_id = _get_project_id(slug)
        milestones = _get_milestones(project_id)
        cutoff_date = None
        fallback_last = False
        if recent_days is not None:
            cutoff_date = datetime.utcnow().date() - timedelta(days=recent_days - 1)
            filtered: List[dict] = []
            for m in milestones:
                end_str = m.get("estimated_finish")
                if end_str:
                    try:
                        end_date = datetime.fromisoformat(end_str.replace("Z", "+00:00")).date()
                    except Exception:
                        end_date = None
                    if end_date and end_date >= cutoff_date:
                        filtered.append(m)
            if not filtered and milestones:
                last = max(
                    milestones,
                    key=lambda m: datetime.fromisoformat(
                        m.get("estimated_finish", "1900-01-01").replace("Z", "+00:00")
                    ).date()
                )
                filtered = [last]
                fallback_last = True
            milestones = filtered

    except (ValueError, TaigaFetchError) as e:
        logger.error(f"Failed to calculate daily WIP for all sprints: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise TaigaFetchError(f"Unexpected error: {e}")















