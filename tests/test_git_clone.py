import os
import tempfile
import shutil
import pytest
from src.core.git_clone import GitRepoCloner, GitCloneError

def test_clone_local_repo(tmp_path):
    #create a fake local git repo
    repo_dir = tmp_path / "fake_repo"
    repo_dir.mkdir()
    (repo_dir / "README.md").write_text("# Test Repo\n")
    # Test
    cloner = GitRepoCloner()
    cloned_path = cloner.clone(str(repo_dir))
    assert os.path.exists(cloned_path)
    assert os.path.isfile(os.path.join(cloned_path, "README.md"))
    cloner.cleanup()
    assert not os.path.exists(cloner.temp_dir or "")

def test_cleanup_removes_temp_dir(tmp_path):
    cloner = GitRepoCloner()
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    cloned_path = cloner.clone(str(repo_dir))
    cloner.cleanup()
    assert cloner.temp_dir is None or not os.path.exists(cloner.temp_dir)

def test_clone_invalid_url():
    cloner = GitRepoCloner()
    with pytest.raises(GitCloneError):
        cloner.clone("https://github.com/invalid/invalid-repo-url-should-fail")
    cloner.cleanup()

def test_clone_valid_public_repo(monkeypatch):
    cloner = GitRepoCloner()
    repo_url = "https://github.com/octocat/Hello-World"
    # Patch Repo.clone_from or subprocess.run to simulate clone
    if hasattr(cloner, 'GITPYTHON_AVAILABLE') and cloner.GITPYTHON_AVAILABLE:
        def fake_clone_from(url, dest):
            os.makedirs(dest, exist_ok=True)
            with open(os.path.join(dest, "README.md"), "w") as f:
                f.write("# Hello World\n")
        monkeypatch.setattr("git.Repo.clone_from", fake_clone_from)
    else:
        def fake_run(args, capture_output, text):
            dest = args[-1]
            os.makedirs(dest, exist_ok=True)
            with open(os.path.join(dest, "README.md"), "w") as f:
                f.write("# Hello World\n")
            return type("Result", (), {"returncode": 0, "stderr": ""})()
        monkeypatch.setattr("subprocess.run", fake_run)
    cloned_path = cloner.clone(repo_url)
    assert os.path.exists(cloned_path)
    assert os.path.isfile(os.path.join(cloned_path, "README.md"))
    cloner.cleanup()