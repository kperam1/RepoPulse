import logging
import requests
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List

from src.metrics.wip import (
    _validate_taiga_url,
    _get_project_id,
    _get_project_statuses,
    _get_milestones,
    _get_userstories,
    _get_tasks,
    _get_userstory_history,
    _get_task_history,
    _categorize_status,
    TaigaFetchError,
    TAIGA_API_BASE,
)

logger = logging.getLogger("repopulse.metrics.taiga_helpers")

TaigaAPIError = TaigaFetchError


def parse_taiga_slug(taiga_url: str) -> str:
    return _validate_taiga_url(taiga_url)


def fetch_taiga_project(slug: str) -> dict:
    project_id = _get_project_id(slug)
    return {"id": project_id, "slug": slug}


def fetch_taiga_statuses(project_id: int, kind: str = "userstory") -> list[dict]:
    if kind == "task":
        from src.metrics.wip import _get_task_statuses
        status_map = _get_task_statuses(project_id)
    else:
        status_map = _get_project_statuses(project_id)
    result = []
    for sid, info in status_map.items():
        result.append({
            "id": sid,
            "name": info.get("name", "Unknown"),
            "is_closed": info.get("is_closed", False),
            "order": info.get("order", 999),
        })
    return result


def fetch_taiga_sprints(project_id: int) -> list[dict]:
    return _get_milestones(project_id)


def fetch_taiga_user_stories(sprint_id: int) -> list[dict]:
    return _get_userstories(project_id=0, milestone=sprint_id)


def fetch_taiga_tasks(project_id: int) -> list[dict]:
    return _get_tasks(project_id)


def fetch_taiga_item_history(kind: str, item_id: int) -> list[dict]:
    if kind == "task":
        return _get_task_history(item_id)
    return _get_userstory_history(item_id)


def derive_wip_done_statuses(statuses: list[dict]) -> tuple[set[str], set[str]]:
    if not statuses:
        return set(), set()
    orders = sorted(set(s.get("order", 999) for s in statuses))
    min_order = orders[0] if orders else 999
    wip_names = set()
    done_names = set()
    for s in statuses:
        name = s.get("name", "")
        if s.get("is_closed", False):
            done_names.add(name)
        elif s.get("order", 999) != min_order:
            wip_names.add(name)
    return wip_names, done_names


def filter_recent_sprints(sprints: list[dict], recent_days: Optional[int] = None) -> list[dict]:
    if recent_days is None:
        return sprints
    cutoff = datetime.now(tz=timezone.utc).date() - timedelta(days=recent_days)
    filtered = []
    for s in sprints:
        end_str = s.get("estimated_finish") or s.get("finish_date", "")
        if end_str:
            try:
                end_date = datetime.fromisoformat(end_str.replace("Z", "+00:00")).date()
                if end_date >= cutoff:
                    filtered.append(s)
            except (ValueError, TypeError):
                filtered.append(s)
        else:
            filtered.append(s)
    return filtered


def find_last_activity_date(tasks: list[dict]) -> Optional[datetime]:
    last = None
    for task in tasks:
        for event in task.get("history", []):
            created_str = event.get("created_at", "")
            if created_str:
                try:
                    dt = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                    if last is None or dt > last:
                        last = dt
                except (ValueError, TypeError):
                    continue
    return last.date() if last else None
