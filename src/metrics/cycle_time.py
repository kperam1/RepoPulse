from datetime import date, timedelta
from typing import Optional


def compute_cycle_times(
    items: list[dict],
    wip_statuses: set[str],
    done_statuses: set[str],
) -> list[dict]:
    results = []
    for item in items:
        ct = _item_cycle_time(item, wip_statuses, done_statuses)
        if ct is not None:
            results.append(ct)
    return results


def compute_daily_cycle_time(
    cycle_times: list[dict],
    start_date: str,
    end_date: str,
) -> list[dict]:
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)

    by_day: dict[str, list[float]] = {}
    current = start
    while current <= end:
        by_day[current.isoformat()] = []
        current += timedelta(days=1)

    for ct in cycle_times:
        done_date = ct["done_date"]
        if done_date in by_day:
            by_day[done_date].append(ct["cycle_time_days"])

    daily = []
    for day_str in sorted(by_day.keys()):
        values = by_day[day_str]
        if not values:
            daily.append({
                "date": day_str,
                "completed_count": 0,
                "total_cycle_time_days": 0.0,
                "average_cycle_time_days": 0.0,
                "median_cycle_time_days": 0.0,
            })
        else:
            sorted_vals = sorted(values)
            n = len(sorted_vals)
            if n % 2 == 1:
                median = sorted_vals[n // 2]
            else:
                median = (sorted_vals[n // 2 - 1] + sorted_vals[n // 2]) / 2.0

            daily.append({
                "date": day_str,
                "completed_count": n,
                "total_cycle_time_days": round(sum(values), 2),
                "average_cycle_time_days": round(sum(values) / n, 2),
                "median_cycle_time_days": round(median, 2),
            })

    return daily


def compute_sprint_cycle_time(
    stories: list[dict],
    wip_status_names: set[str],
    done_status_names: set[str],
    start_date: str,
    end_date: str,
) -> dict:
    items = _convert_taiga_stories(stories)
    cycle_times = compute_cycle_times(items, wip_status_names, done_status_names)
    daily = compute_daily_cycle_time(cycle_times, start_date, end_date)
    return {
        "item_cycle_times": cycle_times,
        "daily_cycle_time": daily,
    }


def _convert_taiga_stories(stories: list[dict]) -> list[dict]:
    items = []
    for story in stories:
        history = story.get("history", [])
        converted_history = []
        for entry in history:
            values_diff = entry.get("values_diff", {})
            status_diff = values_diff.get("status")
            if not status_diff:
                continue
            if not isinstance(status_diff, list) or len(status_diff) != 2:
                continue
            converted_history.append({
                "created_at": entry.get("created_at", ""),
                "values_diff": {"status": status_diff},
            })
        items.append({
            "id": story.get("id"),
            "ref": story.get("ref"),
            "subject": story.get("subject", ""),
            "history": converted_history,
        })
    return items


def _item_cycle_time(
    item: dict,
    wip_statuses: set[str],
    done_statuses: set[str],
) -> Optional[dict]:
    history = item.get("history", [])
    if not history:
        return None

    transitions = _extract_status_transitions(history)
    if not transitions:
        return None

    started_at = _find_first_wip_entry(transitions, wip_statuses)
    if started_at is None:
        return None

    done_at = _find_final_done_entry(transitions, done_statuses, started_at)
    if done_at is None:
        return None

    cycle_days = (done_at - started_at).total_seconds() / 86400.0

    return {
        "item_id": item.get("id"),
        "item_ref": item.get("ref"),
        "item_subject": item.get("subject", ""),
        "started_date": started_at.isoformat()[:10],
        "done_date": done_at.isoformat()[:10],
        "cycle_time_days": round(cycle_days, 2),
    }


def _extract_status_transitions(history: list[dict]) -> list[dict]:
    transitions = []
    for entry in history:
        values_diff = entry.get("values_diff", {})
        status_diff = values_diff.get("status")
        if not status_diff:
            continue
        if not isinstance(status_diff, list) or len(status_diff) != 2:
            continue
        transitions.append({
            "timestamp": entry.get("created_at", ""),
            "from_status": status_diff[0],
            "to_status": status_diff[1],
        })
    transitions.sort(key=lambda t: t["timestamp"])
    return transitions


def _find_first_wip_entry(
    transitions: list[dict],
    wip_statuses: set[str],
) -> Optional[date]:
    for t in transitions:
        if t["to_status"] in wip_statuses:
            ts = t["timestamp"]
            try:
                return date.fromisoformat(ts[:10])
            except (ValueError, TypeError):
                continue
    return None


def _find_final_done_entry(
    transitions: list[dict],
    done_statuses: set[str],
    started_at: date,
) -> Optional[date]:
    done_at = None
    for t in transitions:
        ts_str = t["timestamp"]
        try:
            ts_date = date.fromisoformat(ts_str[:10])
        except (ValueError, TypeError):
            continue
        if ts_date < started_at:
            continue
        if t["to_status"] in done_statuses:
            done_at = ts_date
    return done_at
