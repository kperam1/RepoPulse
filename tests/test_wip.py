import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta, date
import requests
from src.metrics.wip import (
    TaigaFetchError,
    DailyWIPMetric,
    WIPMetric,
    _validate_taiga_url,
    _get_project_id,
    _get_project_statuses,
    _get_userstories,
    _get_userstory_history,
    _get_sprint_dates,
    _extract_status_at_date,
    _categorize_status,
    _get_milestones,
    calculate_daily_wip,
    calculate_daily_wip_all_sprints,
)


class TestValidateTaigaUrl:
    def test_valid_url(self):
        url = "https://taiga.io/project/my-project"
        assert _validate_taiga_url(url) == "my-project"

    def test_valid_url_with_slash(self):
        url = "https://taiga.io/project/my-project/"
        assert _validate_taiga_url(url) == "my-project"

    def test_empty_url(self):
        with pytest.raises(ValueError):
            _validate_taiga_url("")

    def test_invalid_url_format(self):
        url = "https://taiga.io/some/path"
        with pytest.raises(ValueError):
            _validate_taiga_url(url)


class TestGetProjectId:
    @patch("src.metrics.wip.requests.get")
    def test_successful_fetch(self, mock_get):
        mock_response = Mock()
        mock_response.json.return_value = {"id": 123}
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        assert _get_project_id("my-project") == 123

    @patch("src.metrics.wip.requests.get")
    def test_project_not_found(self, mock_get):
        mock_response = Mock()
        mock_response.json.return_value = {}
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        with pytest.raises(TaigaFetchError):
            _get_project_id("nonexistent")

    @patch("src.metrics.wip.requests.get")
    def test_request_exception(self, mock_get):
        mock_get.side_effect = requests.RequestException("Network error")

        with pytest.raises(TaigaFetchError):
            _get_project_id("my-project")

    @patch("src.metrics.wip.requests.get")
    def test_project_missing_id(self, mock_get):
        mock_response = Mock()
        mock_response.json.return_value = {"name": "my-project"}
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        with pytest.raises(TaigaFetchError):
            _get_project_id("my-project")


class TestGetProjectStatuses:
    @patch("src.metrics.wip.requests.get")
    def test_successful_fetch(self, mock_get):
        mock_response = Mock()
        mock_response.json.return_value = [
            {"id": 1, "name": "Backlog", "is_closed": False, "order": 1},
            {"id": 2, "name": "Done", "is_closed": True, "order": 3},
        ]
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        statuses = _get_project_statuses(123)
        assert len(statuses) == 2
        assert statuses[1]["name"] == "Backlog"

    @patch("src.metrics.wip.requests.get")
    def test_empty_response(self, mock_get):
        mock_response = Mock()
        mock_response.json.return_value = []
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        with pytest.raises(TaigaFetchError):
            _get_project_statuses(123)

    @patch("src.metrics.wip.requests.get")
    def test_unexpected_response(self, mock_get):
        mock_response = Mock()
        mock_response.json.return_value = 123  # Not iterable
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        with pytest.raises(TaigaFetchError):
            _get_project_statuses(123)


class TestGetUserstories:
    @patch("src.metrics.wip.requests.get")
    def test_successful_fetch(self, mock_get):
        mock_response = Mock()
        mock_response.json.return_value = [
            {"id": 1, "title": "Story 1"},
            {"id": 2, "title": "Story 2"},
        ]
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        stories = _get_userstories(123)
        assert len(stories) == 2

    @patch("src.metrics.wip.requests.get")
    def test_empty_response(self, mock_get):
        mock_response = Mock()
        mock_response.json.return_value = []
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        assert _get_userstories(123) == []

    @patch("src.metrics.wip.requests.get")
    def test_non_list_response(self, mock_get):
        mock_response = Mock()
        mock_response.json.return_value = {"items": []}
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        assert _get_userstories(123) == []


class TestGetUserstoryHistory:
    @patch("src.metrics.wip.requests.get")
    def test_successful_fetch(self, mock_get):
        mock_response = Mock()
        mock_response.json.return_value = [
            {
                "id": 1,
                "created_at": "2024-01-01T10:00:00Z",
                "values_diff": {"status": [1, "Backlog", 2, "In Progress"]},
            }
        ]
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        history = _get_userstory_history(1)
        assert len(history) == 1

    @patch("src.metrics.wip.requests.get")
    def test_request_exception_returns_empty(self, mock_get):
        mock_get.side_effect = requests.RequestException("Not found")

        history = _get_userstory_history(1)
        assert history == []


class TestGetSprintDates:
    @patch("src.metrics.wip.requests.get")
    def test_successful_fetch(self, mock_get):
        mock_response = Mock()
        mock_response.json.return_value = {
            "id": 1,
            "estimated_start": "2024-01-01T00:00:00Z",
            "estimated_finish": "2024-01-14T00:00:00Z",
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        start, end = _get_sprint_dates(123, 1)
        assert start == date(2024, 1, 1)
        assert end == date(2024, 1, 14)

    @patch("src.metrics.wip.requests.get")
    def test_missing_dates(self, mock_get):
        mock_response = Mock()
        mock_response.json.return_value = {"id": 1}
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        with pytest.raises(TaigaFetchError):
            _get_sprint_dates(123, 1)


class TestExtractStatusAtDate:
    def test_status_before_any_event(self):
        target_date = date(2024, 1, 1)
        history = [
            {
                "created_at": "2024-01-02T10:00:00Z",
                "values_diff": {"status": [None, None, 1, "Backlog"]},
            }
        ]

        assert _extract_status_at_date(history, target_date) is None

    def test_status_after_event(self):
        target_date = date(2024, 1, 2)
        history = [
            {
                "created_at": "2024-01-01T10:00:00Z",
                "values_diff": {"status": [None, None, 2, "In Progress"]},
            }
        ]

        assert _extract_status_at_date(history, target_date) == 2

    def test_multiple_events_returns_latest(self):
        target_date = date(2024, 1, 3)
        history = [
            {
                "created_at": "2024-01-01T10:00:00Z",
                "values_diff": {"status": [None, None, 1, "Backlog"]},
            },
            {
                "created_at": "2024-01-02T10:00:00Z",
                "values_diff": {"status": [1, "Backlog", 2, "In Progress"]},
            },
            {
                "created_at": "2024-01-04T10:00:00Z",
                "values_diff": {"status": [2, "In Progress", 3, "Done"]},
            },
        ]

        assert _extract_status_at_date(history, target_date) == 2

    def test_empty_history(self):
        assert _extract_status_at_date([], date(2024, 1, 1)) is None

    def test_no_status_changes(self):
        target_date = date(2024, 1, 1)
        history = [
            {
                "created_at": "2024-01-01T10:00:00Z",
                "values_diff": {"title": ["Old", "New"]},
            }
        ]

        assert _extract_status_at_date(history, target_date) is None
    def test_invalid_status_change_format(self):
        target_date = date(2024, 1, 1)
        history = [
            {
                "created_at": "2024-01-01T10:00:00Z",
                "values_diff": {"status": [1, 2]},  # len < 3
            }
        ]

        assert _extract_status_at_date(history, target_date) is None

class TestCategorizeStatus:
    def test_none_status_is_backlog(self):
        status_map = {1: {"is_closed": False, "order": 1}}
        assert _categorize_status(None, status_map) == "backlog"

    def test_closed_status_is_done(self):
        status_map = {3: {"is_closed": True, "order": 3}}
        assert _categorize_status(3, status_map) == "done"

    def test_first_status_is_backlog(self):
        status_map = {
            1: {"is_closed": False, "order": 1},
            2: {"is_closed": False, "order": 2},
        }
        assert _categorize_status(1, status_map, min_order=1) == "backlog"

    def test_middle_status_is_wip(self):
        status_map = {
            1: {"is_closed": False, "order": 1},
            2: {"is_closed": False, "order": 2},
        }
        assert _categorize_status(2, status_map, min_order=1) == "wip"

    def test_unknown_status_is_wip(self):
        status_map = {1: {"is_closed": False, "order": 1}}
        assert _categorize_status(999, status_map) == "wip"

    def test_min_order_calculation(self):
        status_map = {
            1: {"is_closed": False, "order": 1},
            2: {"is_closed": False, "order": 2},
        }
        # When min_order is None, it should calculate min_order and categorize accordingly
        assert _categorize_status(2, status_map) == "wip"


class TestGetMilestones:
    @patch("src.metrics.wip.requests.get")
    def test_successful_fetch_with_results_key(self, mock_get):
        mock_response = Mock()
        mock_response.json.return_value = {
            "results": [
                {"id": 1, "name": "Sprint 1"},
                {"id": 2, "name": "Sprint 2"},
            ]
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        milestones = _get_milestones(123)
        assert len(milestones) == 2

    @patch("src.metrics.wip.requests.get")
    def test_successful_fetch_list_response(self, mock_get):
        mock_response = Mock()
        mock_response.json.return_value = [{"id": 1, "name": "Sprint 1"}]
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        milestones = _get_milestones(123)
        assert len(milestones) == 1

    @patch("src.metrics.wip.requests.get")
    def test_request_exception(self, mock_get):
        mock_get.side_effect = requests.RequestException("Network error")

        with pytest.raises(TaigaFetchError):
            _get_milestones(123)

    @patch("src.metrics.wip.requests.get")
    def test_empty_response(self, mock_get):
        mock_response = Mock()
        mock_response.json.return_value = {"results": []}
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        assert _get_milestones(123) == []


class TestCalculateDailyWip:
    @patch("src.metrics.wip._get_userstory_history")
    @patch("src.metrics.wip._get_userstories")
    @patch("src.metrics.wip._get_project_statuses")
    @patch("src.metrics.wip._get_sprint_dates")
    @patch("src.metrics.wip._get_project_id")
    @patch("src.metrics.wip._validate_taiga_url")
    def test_successful_calculation(
        self,
        mock_validate,
        mock_project_id,
        mock_sprint_dates,
        mock_statuses,
        mock_stories,
        mock_history,
    ):
        mock_validate.return_value = "my-project"
        mock_project_id.return_value = 123
        mock_sprint_dates.return_value = (date(2024, 1, 1), date(2024, 1, 3))
        mock_statuses.return_value = {
            1: {"name": "Backlog", "is_closed": False, "order": 1},
            2: {"name": "In Progress", "is_closed": False, "order": 2},
        }
        mock_stories.return_value = [
            {"id": 1, "status": 2, "created_date": "2024-01-01T00:00:00Z"}
        ]
        mock_history.return_value = []

        metric = calculate_daily_wip("https://taiga.io/project/my-project", 1)

        assert metric.project_id == 123
        assert metric.project_slug == "my-project"
        assert metric.sprint_id == 1
        assert len(metric.daily_wip) == 3

    @patch("src.metrics.wip._validate_taiga_url")
    def test_invalid_url(self, mock_validate):
        mock_validate.side_effect = ValueError("Invalid URL")

        with pytest.raises(ValueError):
            calculate_daily_wip("invalid-url", 1)


class TestCalculateDailyWipAllSprints:
    @patch("src.metrics.wip._validate_taiga_url")
    def test_invalid_url_raises(self, mock_validate):
        mock_validate.side_effect = ValueError("Invalid URL")

        with pytest.raises(ValueError):
            calculate_daily_wip_all_sprints("invalid-url")


class TestDataClasses:
    def test_daily_wip_metric(self):
        metric = DailyWIPMetric(
            date="2024-01-01", wip_count=5, backlog_count=10, done_count=3
        )
        assert metric.wip_count == 5
        assert metric.backlog_count == 10

    def test_wip_metric(self):
        daily_wip = [DailyWIPMetric("2024-01-01", 5, 10, 0)]
        metric = WIPMetric(
            project_id=123,
            project_slug="my-project",
            sprint_id=1,
            daily_wip=daily_wip,
        )
        assert len(metric.daily_wip) == 1
        assert metric.project_id == 123


class TestTaigaFetchError:
    def test_exception_creation(self):
        error = TaigaFetchError("Test error")
        assert str(error) == "Test error"

    def test_exception_raise(self):
        with pytest.raises(TaigaFetchError):
            raise TaigaFetchError("Test")
