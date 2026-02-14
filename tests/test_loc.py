import os
import tempfile
import shutil

import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.metrics.loc import (
    count_loc_in_content,
    count_loc_in_file,
    count_loc_in_directory,
    is_supported_file,
)

client = TestClient(app)
SAMPLE_DIR = os.path.join(os.path.dirname(__file__), "sample_files")


def _sample_path(*parts):
    return os.path.join(SAMPLE_DIR, *parts)


class TestJavaFileLOC:

    def test_calculator_java_loc(self):
        result = count_loc_in_file(
            _sample_path("java_project", "src", "com", "example", "Calculator.java")
        )
        assert result is not None
        assert result.total_lines > 0
        assert result.loc > 0
        assert result.blank_lines > 0
        assert result.excluded_lines > 0
        assert result.loc < result.total_lines
        assert result.loc + result.blank_lines + result.excluded_lines == result.total_lines

    def test_main_java_loc(self):
        result = count_loc_in_file(
            _sample_path("java_project", "src", "com", "example", "Main.java")
        )
        assert result is not None
        assert result.total_lines == 11
        assert result.loc + result.blank_lines + result.excluded_lines == result.total_lines

    def test_stringhelper_java_loc(self):
        result = count_loc_in_file(
            _sample_path("java_project", "src", "com", "example", "util", "StringHelper.java")
        )
        assert result is not None
        assert result.loc > 0
        assert result.loc + result.blank_lines + result.excluded_lines == result.total_lines


class TestPythonFileLOC:

    def test_calculator_py_loc(self):
        result = count_loc_in_file(_sample_path("python_project", "calculator.py"))
        assert result is not None
        assert result.total_lines > 0
        assert result.loc > 0
        assert result.blank_lines >= 1
        assert result.loc + result.blank_lines + result.excluded_lines == result.total_lines

    def test_main_py_loc(self):
        result = count_loc_in_file(_sample_path("python_project", "main.py"))
        assert result is not None
        assert result.loc > 0
        assert result.loc + result.blank_lines + result.excluded_lines == result.total_lines


class TestTypeScriptFileLOC:

    def test_calculator_ts_loc(self):
        result = count_loc_in_file(_sample_path("ts_project", "src", "calculator.ts"))
        assert result is not None
        assert result.total_lines == 24
        assert result.loc > 0
        assert result.excluded_lines > 0
        assert result.loc + result.blank_lines + result.excluded_lines == result.total_lines

    def test_index_ts_loc(self):
        result = count_loc_in_file(_sample_path("ts_project", "src", "index.ts"))
        assert result is not None
        assert result.loc > 0
        assert result.loc + result.blank_lines + result.excluded_lines == result.total_lines


class TestCountLOCInContent:

    def test_empty_content(self):
        result = count_loc_in_content("")
        assert result.total_lines == 0
        assert result.loc == 0

    def test_only_blank_lines(self):
        result = count_loc_in_content("\n\n\n")
        assert result.loc == 0
        assert result.blank_lines == 3

    def test_only_braces(self):
        content = "{\n}\n  {  \n  }  \n"
        result = count_loc_in_content(content)
        assert result.loc == 0
        assert result.excluded_lines == 4

    def test_mixed_content(self):
        content = (
            "package com.example;\n"
            "\n"
            "public class Foo {\n"
            "\n"
            "    int x = 1;\n"
            "    \n"
            "}\n"
        )
        result = count_loc_in_content(content)
        assert result.loc == 3
        assert result.blank_lines == 3
        assert result.excluded_lines == 1
        assert result.total_lines == 7

    def test_whitespace_only_lines(self):
        content = "  \n\t\n   \t   \n"
        result = count_loc_in_content(content)
        assert result.loc == 0
        assert result.blank_lines == 3


class TestDirectoryScanning:

    def test_java_project_packages(self):
        project = count_loc_in_directory(_sample_path("java_project"))
        assert project.total_files == 3
        assert project.total_loc > 0
        assert len(project.packages) == 2

        pkg_names = {p.package for p in project.packages}
        assert any("example" in p and "util" not in p for p in pkg_names)
        assert any("util" in p for p in pkg_names)

    def test_python_project_scope(self):
        project = count_loc_in_directory(_sample_path("python_project"))
        assert project.total_files == 2
        assert project.total_loc > 0
        assert len(project.packages) == 1

    def test_ts_project_scope(self):
        project = count_loc_in_directory(_sample_path("ts_project"))
        assert project.total_files == 2
        assert project.total_loc > 0
        assert len(project.packages) == 1

    def test_project_totals_equal_sum_of_files(self):
        project = count_loc_in_directory(_sample_path("java_project"))
        assert project.total_loc == sum(f.loc for f in project.files)

    def test_project_totals_equal_sum_of_packages(self):
        project = count_loc_in_directory(_sample_path("java_project"))
        assert project.total_loc == sum(p.loc for p in project.packages)


class TestEdgeCases:

    def test_unsupported_extension_ignored(self):
        assert is_supported_file("readme.md") is False
        assert is_supported_file("data.json") is False
        assert is_supported_file("Makefile") is False

    def test_supported_extensions(self):
        assert is_supported_file("App.java") is True
        assert is_supported_file("main.py") is True
        assert is_supported_file("index.ts") is True

    def test_count_loc_returns_none_for_unsupported(self):
        with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False) as f:
            f.write("Hello world\n")
            tmp_path = f.name
        try:
            assert count_loc_in_file(tmp_path) is None
        finally:
            os.unlink(tmp_path)

    def test_empty_directory(self):
        tmp_dir = tempfile.mkdtemp()
        try:
            project = count_loc_in_directory(tmp_dir)
            assert project.total_loc == 0
            assert project.total_files == 0
            assert len(project.packages) == 0
        finally:
            shutil.rmtree(tmp_dir)


class TestLOCEndpoint:

    def test_loc_endpoint_with_java_project(self):
        abs_path = os.path.abspath(_sample_path("java_project"))
        response = client.post("/metrics/loc", json={"repo_path": abs_path})
        assert response.status_code == 200
        data = response.json()
        assert data["total_files"] == 3
        assert data["total_loc"] > 0
        assert len(data["packages"]) == 2
        assert len(data["files"]) == 3

    def test_loc_endpoint_invalid_path(self):
        response = client.post("/metrics/loc", json={"repo_path": "/nonexistent/path/to/repo"})
        assert response.status_code == 404

    def test_loc_endpoint_missing_field(self):
        response = client.post("/metrics/loc", json={})
        assert response.status_code == 400 or response.status_code == 422

    def test_loc_endpoint_relative_path_rejected(self):
        response = client.post("/metrics/loc", json={"repo_path": "relative/path"})
        assert response.status_code == 400 or response.status_code == 422
