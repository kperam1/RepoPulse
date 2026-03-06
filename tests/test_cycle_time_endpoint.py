from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)

MOCK_PROJECT = {"id": 100, "slug": "test-project"}

MOCK_STATUSES = [
    {"id": 1, "name": "New", "order": 1, "is_closed": False},
    {"id": 2, "name": "In Progress", "order": 2, "is_closed": False},
    {"id": 3, "name": "Done", "order": 3, "is_closed": True},
]

MOCK_SPRINT = {
    "id": 10,
    "name": "Sprint 1",
    "estimated_start": "2026-03-01",
    "estimated_finish": "2026-03-14",
}

MOCK_STORIES = [
    {
        "id": 1,
        "ref": 101,
        "subject": "Feature A",
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
        "subject": "Feature B",
        "history": [
            {
                "created_at": "2026-03-03T09:00:00Z",
                "values_diff": {"status": ["New", "In Progress"]},
            },
        ],
    },
]

MOCK_TASKS = [
    {
        "id": 1,
        "ref": 201,
        "subject": "Task A",
        "history": [
            {
                "created_at": "2026-03-01T10:00:00Z",
                "values_diff": {"status": ["New", "In Progress"]},
            },
            {
                "created_at": "2026-03-04T10:00:00Z",
                "values_diff": {"status": ["In Progress", "Done"]},
            },
        ],
    },
]


def _derive_statuses(statuses):
    wip = set()
    done = set()
    sorted_s = sorted(statuses, key=lambda s: s["order"])
    for i, s in enumerate(sorted_s):
        if s.get("is_closed"):
            done.add(s["name"])
        elif i > 0:
            wip.add(s["name"])
    return wip, done


class TestCycleTimeEndpointScrum:

    @patch("src.api.routes.find_last_activity_date")
    @patch("src.api.routes.fetch_taiga_item_history")
    @patch("src.api.routes.fetch_taiga_user_stories")
    @patch("src.api.routes.filter_recent_sprints")
    @patch("src.api.routes.fetch_taiga_sprints")
    @patch("src.api.routes.derive_wip_done_statuses")
    @patch("src.api.routes.fetch_taiga_statuses")
    @patch("src.api.routes.fetch_taiga_project")
    @patch("src.api.routes.parse_taiga_slug")
    def test_scrum_cycle_time(
        self, mock_slug, mock_project, mock_statuses, mock_derive,
        mock_sprints, mock_filter, mock_stories, mock_history, mock_activity,
    ):
        mock_slug.return_value = "test-project"
        mock_project.return_value = MOCK_PROJECT
        mock_statuses.return_value = MOCK_STATUSES
        mock_derive.return_value = ({"In Progress"}, {"Done"})
        mock_sprints.return_value = [MOCK_SPRINT]
        mock_filter.return_value = [MOCK_SPRINT]
        mock_stories.return_value = MOCK_STORIES
        mock_history.side_effect = lambda kind, item_id: next(
            s["history"] for s in MOCK_STORIES if s["id"] == item_id
        )

        response = client.post(
            "/metrics/cycle-time",
            json={"taiga_url": "https://tree.taiga.io/project/test-project", "recent_days": 30},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["project_id"] == 100
        assert data["project_slug"] == "test-project"
        assert data["sprints_count"] == 1
        assert len(data["sprints"]) == 1

        sprint = data["sprints"][0]
        assert sprint["sprint_id"] == 10
        assert sprint["sprint_name"] == "Sprint 1"
        assert len(sprint["item_cycle_times"]) == 1
        assert sprint["item_cycle_times"][0]["item_ref"] == 101
        assert sprint["item_cycle_times"][0]["cycle_time_days"] == 3.0
        assert len(sprint["daily_cycle_time"]) > 0


class TestCycleTimeEndpointKanban:

    @patch("src.api.routes.find_last_activity_date")
    @patch("src.api.routes.fetch_taiga_item_history")
    @patch("src.api.routes.fetch_taiga_tasks")
    @patch("src.api.routes.derive_wip_done_statuses")
    @patch("src.api.routes.fetch_taiga_statuses")
    @patch("src.api.routes.fetch_taiga_project")
    @patch("src.api.routes.parse_taiga_slug")
    def test_kanban_cycle_time(
        self, mock_slug, mock_project, mock_statuses, mock_derive,
        mock_tasks, mock_history, mock_activity,
    ):
        mock_slug.return_value = "test-project"
        mock_project.return_value = MOCK_PROJECT
        mock_statuses.return_value = MOCK_STATUSES
        mock_derive.return_value = ({"In Progress"}, {"Done"})
        mock_tasks.return_value = MOCK_TASKS
        mock_history.side_effect = lambda kind, item_id: MOCK_TASKS[0]["history"]
        mock_activity.return_value = None

        response = client.post(
            "/metrics/cycle-time",
            json={"kanban_url": "https://tree.taiga.io/project/test-project"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["project_id"] == 100
        assert data["sprints_count"] == 1

        sprint = data["sprints"][0]
        assert sprint["sprint_name"] == "kanban"
        assert sprint["sprint_id"] is None
        assert len(sprint["item_cycle_times"]) == 1
        assert sprint["item_cycle_times"][0]["cycle_time_days"] == 3.0


class TestCycleTimeEndpointErrors:

    def test_missing_url(self):
        response = client.post("/metrics/cycle-time", json={})
        assert response.status_code == 400

    @patch("src.api.routes.parse_taiga_slug")
    def test_bad_url(self, mock_slug):
        mock_slug.side_effect = ValueError("Invalid Taiga URL")
        response = client.post(
            "/metrics/cycle-time",
            json={"taiga_url": "not-a-url"},
        )
        assert response.status_code == 400

    @patch("src.api.routes.parse_taiga_slug")
    @patch("src.api.routes.fetch_taiga_project")
    def test_taiga_api_down(self, mock_project, mock_slug):
        from src.metrics.taiga_helpers import TaigaAPIError
        mock_slug.return_value = "test-project"
        mock_project.side_effect = TaigaAPIError("Connection refused")
        response = client.post(
            "/metrics/cycle-time",
            json={"taiga_url": "https://tree.taiga.io/project/test-project"},
        )
        assert response.status_code == 503

    @patch("src.api.routes.fetch_taiga_sprints")
    @patch("src.api.routes.derive_wip_done_statuses")
    @patch("src.api.routes.fetch_taiga_statuses")
    @patch("src.api.routes.fetch_taiga_project")
    @patch("src.api.routes.parse_taiga_slug")
    def test_no_sprints_found(
        self, mock_slug, mock_project, mock_statuses, mock_derive, mock_sprints,
    ):
        mock_slug.return_value = "test-project"
        mock_project.return_value = MOCK_PROJECT
        mock_statuses.return_value = MOCK_STATUSES
        mock_derive.return_value = ({"In Progress"}, {"Done"})
        mock_sprints.return_value = []
        response = client.post(
            "/metrics/cycle-time",
            json={"taiga_url": "https://tree.taiga.io/project/test-project"},
        )
        assert response.status_code == 404


class TestCycleTimeKanbanPriority:

    @patch("src.api.routes.find_last_activity_date")
    @patch("src.api.routes.fetch_taiga_item_history")
    @patch("src.api.routes.fetch_taiga_tasks")
    @patch("src.api.routes.derive_wip_done_statuses")
    @patch("src.api.routes.fetch_taiga_statuses")
    @patch("src.api.routes.fetch_taiga_project")
    @patch("src.api.routes.parse_taiga_slug")
    def test_kanban_takes_priority_over_taiga_url(
        self, mock_slug, mock_project, mock_statuses, mock_derive,
        mock_tasks, mock_history, mock_activity,
    ):
        mock_slug.return_value = "test-project"
        mock_project.return_value = MOCK_PROJECT
        mock_statuses.return_value = MOCK_STATUSES
        mock_derive.return_value = ({"In Progress"}, {"Done"})
        mock_tasks.return_value = MOCK_TASKS
        mock_history.side_effect = lambda kind, item_id: MOCK_TASKS[0]["history"]
        mock_activity.return_value = None

        response = client.post(
            "/metrics/cycle-time",
            json={
                "taiga_url": "https://tree.taiga.io/project/scrum-project",
                "kanban_url": "https://tree.taiga.io/project/test-project",
            },
        )

        assert response.status_code == 200
        data = response.json()
        sprint = data["sprints"][0]
        assert sprint["sprint_name"] == "kanban"
