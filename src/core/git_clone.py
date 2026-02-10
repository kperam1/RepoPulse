import os
import shutil
import tempfile
from typing import Optional

try:
    from git import Repo, GitCommandError
    GITPYTHON_AVAILABLE = True
except ImportError:
    import subprocess
    GITPYTHON_AVAILABLE = False

class GitCloneError(Exception):
    pass

class GitRepoCloner:
    def __init__(self):
        self.temp_dir: Optional[str] = None

    def clone(self, repo_url_or_path: str) -> str:
        """
        Clones a public GitHub repository or copies a local repo to a temp directory.
        Returns the path to the cloned/copied repo.
        Raises GitCloneError on failure.
        """
        self.temp_dir = tempfile.mkdtemp(prefix="repopulse_clone_")
        try:
            if os.path.isdir(repo_url_or_path):
                #copy
                shutil.copytree(repo_url_or_path, os.path.join(self.temp_dir, os.path.basename(repo_url_or_path)))
                return os.path.join(self.temp_dir, os.path.basename(repo_url_or_path))
            else:
                #clone
                dest = os.path.join(self.temp_dir, "repo")
                if GITPYTHON_AVAILABLE:
                    Repo.clone_from(repo_url_or_path, dest)
                else:
                    result = subprocess.run([
                        "git", "clone", repo_url_or_path, dest
                    ], capture_output=True, text=True)
                    if result.returncode != 0:
                        raise GitCloneError(f"Git clone failed: {result.stderr}")
                return dest
        except Exception as e:
            self.cleanup()
            raise GitCloneError(f"Failed to clone repo: {e}")

    def cleanup(self):
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
            self.temp_dir = None