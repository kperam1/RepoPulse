import os
import shutil
import subprocess
import tempfile
from typing import Optional

class GitCloneError(Exception):
    pass

class GitRepoCloner:
    def __init__(self):
        self.temp_dir: Optional[str] = None

    def clone(self, repo_url_or_path: str, shallow: bool = True) -> str:
        """Clone a GitHub repo (or copy a local dir) into a temp directory.
        Returns the path to the cloned repo. Raises GitCloneError on failure."""
        self.temp_dir = tempfile.mkdtemp(prefix="repopulse_clone_")
        try:
            dest_path = os.path.join(self.temp_dir, os.path.basename(repo_url_or_path))
            if os.path.isdir(repo_url_or_path):
                # Handle existing destination directory
                shutil.copytree(
                    repo_url_or_path,
                    dest_path,
                    dirs_exist_ok=True
                )
                return dest_path
            else:
                # remote URL — clone it
                dest = os.path.join(self.temp_dir, "repo")
                env = os.environ.copy()
                env["GIT_TERMINAL_PROMPT"] = "0"   # don't prompt for creds
                cmd = ["git", "clone"]
                if shallow:
                    cmd += ["--depth", "1"]
                cmd += [repo_url_or_path, dest]
                result = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=120, env=env,
                )
                if result.returncode != 0:
                    raise GitCloneError(f"Git clone failed: {result.stderr.strip()}")
                return dest
        except GitCloneError:
            self.cleanup()
            raise
        except Exception as e:
            self.cleanup()
            raise GitCloneError(f"Failed to clone repo: {e}")

    def cleanup(self):
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
            self.temp_dir = None