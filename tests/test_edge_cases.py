"""Tests for less common situations in the scanner and baseline code."""

import json
import os
from unittest import mock

import pytest

from integritywatch.baseline import BaselineError, load_baseline
from integritywatch.scanner import scan_paths


def test_baseline_without_read_permission_raises(tmp_path):
    path = tmp_path / "b.json"
    path.write_text("{}")
    with mock.patch("builtins.open", side_effect=PermissionError):
        with pytest.raises(BaselineError, match="no permission"):
            load_baseline(str(path))


def test_baseline_missing_a_required_key_raises(tmp_path):
    path = tmp_path / "b.json"
    path.write_text(json.dumps({"version": 1, "paths": [], "excludes": []}))
    with pytest.raises(BaselineError, match="missing 'files'"):
        load_baseline(str(path))


def test_single_file_can_be_scanned_directly(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("x")
    entries, errors = scan_paths([str(f)])
    assert list(entries) == [str(f)]
    assert errors == []


def test_excluded_single_file_is_skipped(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("x")
    entries, _errors = scan_paths([str(f)], excludes=["*.txt"])
    assert entries == {}


def test_special_files_are_ignored(tmp_path):
    os.mkfifo(tmp_path / "pipe")
    (tmp_path / "a.txt").write_text("x")
    entries, errors = scan_paths([str(tmp_path)])
    assert [os.path.basename(p) for p in entries] == ["a.txt"]
    assert errors == []


def test_unreadable_file_becomes_an_error_not_a_crash(tmp_path):
    (tmp_path / "a.txt").write_text("x")
    denied = PermissionError(13, "Permission denied")
    with mock.patch("integritywatch.scanner.hash_file", side_effect=denied):
        entries, errors = scan_paths([str(tmp_path)])
    assert entries == {}
    assert len(errors) == 1
    assert "Permission denied" in errors[0]


def test_folder_that_cannot_be_entered_becomes_an_error(tmp_path):
    def fake_walk(_top, onerror=None):
        onerror(OSError(13, "Permission denied", "/secret"))
        return iter([])

    with mock.patch("integritywatch.scanner.os.walk", fake_walk):
        entries, errors = scan_paths([str(tmp_path)])
    assert entries == {}
    assert errors == ["/secret: Permission denied"]
