import pytest

from src.metrics.churn import compute_commit_churn


def test_compute_commit_churn_additions_only(tmp_path):
    repo = tmp_path
    compute_commit_churn(str(repo), "dummysha")