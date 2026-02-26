import os
import subprocess


def compute_commit_churn(repo_path: str, sha: str) -> dict:
    if not os.path.isdir(repo_path):
        raise ValueError(f"Repository path does not exist: {repo_path}")

    if not os.path.isdir(os.path.join(repo_path, ".git")):
        raise ValueError(f"Not a git repository (missing .git): {repo_path}")

    cmd = [
        "git",
        "--no-pager",
        "-C",
        repo_path,
        "show",
        "--numstat",
        "--format=",
        sha,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise ValueError(f"git show failed: {result.stderr.strip()}")

    added = 0
    deleted = 0

    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue

        parts = line.split("\t")
        if len(parts) < 3:
            continue

        a_str, d_str = parts[0].strip(), parts[1].strip()

        if a_str == "-" or d_str == "-":
            continue

        try:
            added += int(a_str)
            deleted += int(d_str)
        except ValueError:
            continue

    modified = min(added, deleted)
    total = added + deleted

    return {
        "added": added,
        "deleted": deleted,
        "modified": modified,
        "total": total,
    }