import os
import subprocess

from src.metrics.churn import compute_commit_churn


def _run(cmd: list[str], cwd: str, env: dict | None = None) -> str:
    full_env = {**os.environ, **(env or {})}
    result = subprocess.run(
        cmd, cwd=cwd, env=full_env, check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def _init_repo(repo: str) -> None:
    _run(["git", "init"], cwd=repo)
    _run(["git", "config", "user.email", "test@example.com"], cwd=repo)
    _run(["git", "config", "user.name", "Test"], cwd=repo)


def test_compute_commit_churn_additions_only(tmp_path):
    repo = str(tmp_path)
    _init_repo(repo)

    # create file with 3 lines and commit it
    p = os.path.join(repo, "a.txt")
    with open(p, "w") as f:
        f.write("line1\nline2\nline3\n")

    _run(["git", "add", "a.txt"], cwd=repo)
    _run(["git", "commit", "-m", "add 3 lines"], cwd=repo)

    sha = _run(["git", "rev-parse", "HEAD"], cwd=repo)

    churn = compute_commit_churn(repo, sha)

    assert churn["added"] == 3
    assert churn["deleted"] == 0
    assert churn["modified"] == 0
    assert churn["total"] == 3