import pytest

from src.metrics.cycle_time import (
    compute_cycle_times,
    compute_daily_cycle_time,
    compute_sprint_cycle_time,
)

WIP = {"In Progress", "Ready for Review"}
DONE = {"Done", "Closed"}


def _make_item(item_id, ref, subject, history):
    return {
        "id": item_id,
        "ref": ref,
        "subject": subject,
        "history": history,
    }


def _make_transition(created_at, from_status, to_status):
    return {
        "created_at": created_at,
        "values_diff": {
            "status": [from_status, to_status],
        },
    }


class TestComputeCycleTimesHappyPath:

    def test_single_item_straight_through(self):
        items = [
            _make_item(1, 101, "Feature A", [
                _make_transition("2026-03-01T10:00:00Z", "New", "In Progress"),
                _make_transition("2026-03-04T15:00:00Z", "In Progress", "Done"),
            ]),
        ]

        results = compute_cycle_times(items, WIP, DONE)

        assert len(results) == 1
        assert results[0]["item_id"] == 1
        assert results[0]["item_ref"] == 101
        assert results[0]["started_date"] == "2026-03-01"
        assert results[0]["done_date"] == "2026-03-04"
        assert results[0]["cycle_time_days"] == 3.0

    def test_multiple_items(self):
        items = [
            _make_item(1, 101, "Fast task", [
                _make_transition("2026-03-01T09:00:00Z", "New", "In Progress"),
                _make_transition("2026-03-02T09:00:00Z", "In Progress", "Done"),
            ]),
            _make_item(2, 102, "Slow task", [
                _make_transition("2026-03-01T09:00:00Z", "New", "In Progress"),
                _make_transition("2026-03-11T09:00:00Z", "In Progress", "Done"),
            ]),
        ]

        results = compute_cycle_times(items, WIP, DONE)

        assert len(results) == 2
        assert results[0]["cycle_time_days"] == 1.0
        assert results[1]["cycle_time_days"] == 10.0


class TestMultipleTransitions:

    def test_item_moves_back_and_forth(self):
        items = [
            _make_item(1, 101, "Bouncy task", [
                _make_transition("2026-03-01T10:00:00Z", "New", "In Progress"),
                _make_transition("2026-03-03T10:00:00Z", "In Progress", "New"),
                _make_transition("2026-03-05T10:00:00Z", "New", "In Progress"),
                _make_transition("2026-03-08T10:00:00Z", "In Progress", "Done"),
            ]),
        ]

        results = compute_cycle_times(items, WIP, DONE)

        assert len(results) == 1
        assert results[0]["started_date"] == "2026-03-01"
        assert results[0]["done_date"] == "2026-03-08"
        assert results[0]["cycle_time_days"] == 7.0

    def test_item_enters_review_then_done(self):
        items = [
            _make_item(1, 101, "Review task", [
                _make_transition("2026-03-01T10:00:00Z", "New", "In Progress"),
                _make_transition("2026-03-03T10:00:00Z", "In Progress", "Ready for Review"),
                _make_transition("2026-03-05T10:00:00Z", "Ready for Review", "Done"),
            ]),
        ]

        results = compute_cycle_times(items, WIP, DONE)

        assert len(results) == 1
        assert results[0]["started_date"] == "2026-03-01"
        assert results[0]["done_date"] == "2026-03-05"


class TestReopenedAfterDone:

    def test_reopened_item_uses_final_done(self):
        items = [
            _make_item(1, 101, "Reopened task", [
                _make_transition("2026-03-01T10:00:00Z", "New", "In Progress"),
                _make_transition("2026-03-03T10:00:00Z", "In Progress", "Done"),
                _make_transition("2026-03-05T10:00:00Z", "Done", "In Progress"),
                _make_transition("2026-03-07T10:00:00Z", "In Progress", "Done"),
            ]),
        ]

        results = compute_cycle_times(items, WIP, DONE)

        assert len(results) == 1
        assert results[0]["started_date"] == "2026-03-01"
        assert results[0]["done_date"] == "2026-03-07"
        assert results[0]["cycle_time_days"] == 6.0


class TestItemNeverDone:

    def test_item_still_in_progress_is_skipped(self):
        items = [
            _make_item(1, 101, "Stuck task", [
                _make_transition("2026-03-01T10:00:00Z", "New", "In Progress"),
            ]),
        ]

        results = compute_cycle_times(items, WIP, DONE)

        assert len(results) == 0

    def test_item_moved_back_to_new_is_skipped(self):
        items = [
            _make_item(1, 101, "Reverted task", [
                _make_transition("2026-03-01T10:00:00Z", "New", "In Progress"),
                _make_transition("2026-03-03T10:00:00Z", "In Progress", "New"),
            ]),
        ]

        results = compute_cycle_times(items, WIP, DONE)

        assert len(results) == 0


class TestItemNeverStarted:

    def test_item_goes_straight_to_done_is_skipped(self):
        items = [
            _make_item(1, 101, "Auto-done task", [
                _make_transition("2026-03-01T10:00:00Z", "New", "Done"),
            ]),
        ]

        results = compute_cycle_times(items, WIP, DONE)

        assert len(results) == 0

    def test_item_with_no_history_is_skipped(self):
        items = [
            _make_item(1, 101, "Empty task", []),
        ]

        results = compute_cycle_times(items, WIP, DONE)

        assert len(results) == 0

    def test_item_only_in_backlog_is_skipped(self):
        items = [
            _make_item(1, 101, "Backlog task", [
                _make_transition("2026-03-01T10:00:00Z", "New", "Backlog"),
            ]),
        ]

        results = compute_cycle_times(items, WIP, DONE)

        assert len(results) == 0


class TestDailyAggregate:

    def test_daily_cycle_time_aggregation(self):
        cycle_times = [
            {"item_id": 1, "done_date": "2026-03-02", "cycle_time_days": 2.0},
            {"item_id": 2, "done_date": "2026-03-02", "cycle_time_days": 4.0},
            {"item_id": 3, "done_date": "2026-03-04", "cycle_time_days": 1.0},
        ]

        daily = compute_daily_cycle_time(cycle_times, "2026-03-01", "2026-03-04")

        assert len(daily) == 4

        day1 = daily[0]
        assert day1["date"] == "2026-03-01"
        assert day1["completed_count"] == 0
        assert day1["average_cycle_time_days"] == 0.0

        day2 = daily[1]
        assert day2["date"] == "2026-03-02"
        assert day2["completed_count"] == 2
        assert day2["average_cycle_time_days"] == 3.0
        assert day2["median_cycle_time_days"] == 3.0
        assert day2["total_cycle_time_days"] == 6.0

        day4 = daily[3]
        assert day4["date"] == "2026-03-04"
        assert day4["completed_count"] == 1
        assert day4["average_cycle_time_days"] == 1.0

    def test_daily_empty_range(self):
        daily = compute_daily_cycle_time([], "2026-03-01", "2026-03-03")

        assert len(daily) == 3
        for d in daily:
            assert d["completed_count"] == 0

    def test_median_with_odd_count(self):
        cycle_times = [
            {"item_id": 1, "done_date": "2026-03-01", "cycle_time_days": 1.0},
            {"item_id": 2, "done_date": "2026-03-01", "cycle_time_days": 3.0},
            {"item_id": 3, "done_date": "2026-03-01", "cycle_time_days": 7.0},
        ]

        daily = compute_daily_cycle_time(cycle_times, "2026-03-01", "2026-03-01")

        assert daily[0]["median_cycle_time_days"] == 3.0

    def test_median_with_even_count(self):
        cycle_times = [
            {"item_id": 1, "done_date": "2026-03-01", "cycle_time_days": 2.0},
            {"item_id": 2, "done_date": "2026-03-01", "cycle_time_days": 4.0},
        ]

        daily = compute_daily_cycle_time(cycle_times, "2026-03-01", "2026-03-01")

        assert daily[0]["median_cycle_time_days"] == 3.0


class TestSprintCycleTime:

    def test_sprint_cycle_time_with_taiga_history(self):
        stories = [
            {
                "id": 1,
                "ref": 101,
                "subject": "Story A",
                "history": [
                    {
                        "created_at": "2026-03-02T10:00:00Z",
                        "values_diff": {"status": ["New", "In Progress"]},
                    },
                    {
                        "created_at": "2026-03-05T15:00:00Z",
                        "values_diff": {"status": ["In Progress", "Done"]},
                    },
                ],
            },
            {
                "id": 2,
                "ref": 102,
                "subject": "Story B (never done)",
                "history": [
                    {
                        "created_at": "2026-03-03T09:00:00Z",
                        "values_diff": {"status": ["New", "In Progress"]},
                    },
                ],
            },
        ]

        result = compute_sprint_cycle_time(
            stories, {"In Progress"}, {"Done"}, "2026-03-01", "2026-03-14",
        )

        assert len(result["item_cycle_times"]) == 1
        assert result["item_cycle_times"][0]["item_ref"] == 101
        assert result["item_cycle_times"][0]["cycle_time_days"] == 3.0
        assert len(result["daily_cycle_time"]) == 14

    def test_sprint_cycle_time_empty_stories(self):
        result = compute_sprint_cycle_time(
            [], {"In Progress"}, {"Done"}, "2026-03-01", "2026-03-07",
        )

        assert result["item_cycle_times"] == []
        assert len(result["daily_cycle_time"]) == 7
        for d in result["daily_cycle_time"]:
            assert d["completed_count"] == 0

    def test_sprint_ignores_non_status_history(self):
        stories = [
            {
                "id": 1,
                "ref": 101,
                "subject": "Story with noise",
                "history": [
                    {
                        "created_at": "2026-03-01T10:00:00Z",
                        "values_diff": {"description": ["old", "new"]},
                    },
                    {
                        "created_at": "2026-03-02T10:00:00Z",
                        "values_diff": {"status": ["New", "In Progress"]},
                    },
                    {
                        "created_at": "2026-03-04T10:00:00Z",
                        "values_diff": {"status": ["In Progress", "Done"]},
                    },
                ],
            },
        ]

        result = compute_sprint_cycle_time(
            stories, {"In Progress"}, {"Done"}, "2026-03-01", "2026-03-07",
        )

        assert len(result["item_cycle_times"]) == 1
        assert result["item_cycle_times"][0]["cycle_time_days"] == 2.0
