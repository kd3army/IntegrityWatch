import json
import os
import stat

import pytest

from integritywatch.baseline import BaselineError, load_baseline, save_baseline


def test_save_and_load_roundtrip(tmp_path):
    path = str(tmp_path / "b.json")
    entries = {"/a": {"type": "file", "sha256": "x", "mode": 420}}
    save_baseline(path, entries, ["/"], ["*.log"])
    data = load_baseline(path)
    assert data["files"] == entries
    assert data["paths"] == ["/"]
    assert data["excludes"] == ["*.log"]


def test_baseline_is_owner_only(tmp_path):
    path = str(tmp_path / "b.json")
    save_baseline(path, {}, [], [])
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600


def test_missing_baseline_raises(tmp_path):
    with pytest.raises(BaselineError, match="run 'init'"):
        load_baseline(str(tmp_path / "nope.json"))


def test_invalid_json_raises(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("not json")
    with pytest.raises(BaselineError, match="not valid JSON"):
        load_baseline(str(path))


def test_wrong_version_raises(tmp_path):
    path = tmp_path / "old.json"
    path.write_text(json.dumps({"version": 99}))
    with pytest.raises(BaselineError, match="unsupported"):
        load_baseline(str(path))
