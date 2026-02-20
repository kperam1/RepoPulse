import logging
import os
import re
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("repopulse.metrics.loc")

SUPPORTED_EXTENSIONS = {".java", ".py", ".ts"}

# matches lines that are empty, whitespace-only, or just a brace
_SKIP_LINE_RE = re.compile(r"^\s*[{}]?\s*$")


@dataclass
class FileLOC:
    path: str
    total_lines: int = 0
    loc: int = 0
    blank_lines: int = 0
    excluded_lines: int = 0


@dataclass
class PackageLOC:
    package: str
    loc: int = 0
    file_count: int = 0
    files: list[FileLOC] = field(default_factory=list)


@dataclass
class ProjectLOC:
    project_root: str = ""
    total_loc: int = 0
    total_files: int = 0
    total_blank_lines: int = 0
    total_excluded_lines: int = 0
    packages: list[PackageLOC] = field(default_factory=list)
    files: list[FileLOC] = field(default_factory=list)


def is_supported_file(filename: str) -> bool:
    _, ext = os.path.splitext(filename)
    return ext.lower() in SUPPORTED_EXTENSIONS


def _should_skip_line(line: str) -> tuple[bool, str]:
    stripped = line.rstrip("\n\r")
    if stripped == "" or stripped.isspace():
        return True, "blank"
    if _SKIP_LINE_RE.match(stripped):
        return True, "excluded"
    return False, "code"


def count_loc_in_content(content: str) -> FileLOC:
    result = FileLOC(path="")
    lines = content.split("\n")

    if lines and lines[-1] == "":
        lines = lines[:-1]

    result.total_lines = len(lines)

    for line in lines:
        skip, reason = _should_skip_line(line)
        if skip:
            if reason == "blank":
                result.blank_lines += 1
            else:
                result.excluded_lines += 1
        else:
            result.loc += 1

    return result


def count_loc_in_file(filepath: str, project_root: str = "") -> Optional[FileLOC]:
    if not is_supported_file(filepath):
        return None

    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except OSError as e:
        logger.warning(f"Cannot read file {filepath}: {e}")
        return None

    result = count_loc_in_content(content)
    result.path = os.path.relpath(filepath, project_root) if project_root else filepath
    return result


SKIP_DIRS = {"node_modules", "__pycache__", "venv", ".venv", "build", "dist"}


def count_loc_in_directory(directory: str) -> ProjectLOC:
    project = ProjectLOC(project_root=directory)
    package_map: dict[str, PackageLOC] = {}

    for dirpath, _dirnames, filenames in os.walk(directory):
        rel_dir = os.path.relpath(dirpath, directory)
        parts = rel_dir.split(os.sep)

        if any((p.startswith(".") and p != ".") or p in SKIP_DIRS for p in parts):
            continue

        for filename in sorted(filenames):
            if not is_supported_file(filename):
                continue

            full_path = os.path.join(dirpath, filename)
            file_loc = count_loc_in_file(full_path, project_root=directory)
            if file_loc is None:
                continue

            project.files.append(file_loc)
            project.total_loc += file_loc.loc
            project.total_files += 1
            project.total_blank_lines += file_loc.blank_lines
            project.total_excluded_lines += file_loc.excluded_lines

            pkg_key = rel_dir if rel_dir != "." else "(root)"
            if pkg_key not in package_map:
                package_map[pkg_key] = PackageLOC(package=pkg_key)
            package_map[pkg_key].loc += file_loc.loc
            package_map[pkg_key].file_count += 1
            package_map[pkg_key].files.append(file_loc)

    project.packages = sorted(package_map.values(), key=lambda p: p.package)

    logger.info(
        f"LOC analysis: {project.total_files} files, "
        f"{project.total_loc} LOC in {len(project.packages)} packages"
    )

    return project
