"""End-to-end tests: run the tool as a real subprocess."""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run(*args):
    return subprocess.run([sys.executable, "-m", "integritywatch", *args],
                          cwd=ROOT, capture_output=True, text=True)


def test_init_then_clean_check(tmp_path):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "a.txt").write_text("hello")
    base = str(tmp_path / "base.json")
    assert run("init", str(tmp_path / "data"), "-b", base).returncode == 0
    result = run("check", "-b", base)
    assert result.returncode == 0
    assert "No changes" in result.stdout


def test_check_detects_modify_delete_new(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    (data / "a.txt").write_text("one")
    (data / "b.txt").write_text("two")
    base = str(tmp_path / "base.json")
    run("init", str(data), "-b", base)

    (data / "a.txt").write_text("changed")
    (data / "b.txt").unlink()
    (data / "c.txt").write_text("new")

    result = run("check", "-b", base)
    assert result.returncode == 1
    assert "[MODIFIED]" in result.stdout
    assert "[DELETED]" in result.stdout
    assert "[NEW]" in result.stdout


def test_check_json_output(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    (data / "a.txt").write_text("one")
    base = str(tmp_path / "base.json")
    run("init", str(data), "-b", base)
    (data / "a.txt").write_text("two")
    result = run("check", "-b", base, "--format", "json")
    report = json.loads(result.stdout)
    assert report["total_changes"] == 1
    assert report["changes"]["modified"][0]["path"].endswith("a.txt")


def test_quiet_prints_nothing_when_clean(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    (data / "a.txt").write_text("one")
    base = str(tmp_path / "base.json")
    run("init", str(data), "-b", base)
    result = run("check", "-b", base, "-q")
    assert result.returncode == 0
    assert result.stdout == ""


def test_baseline_inside_scanned_folder_is_ignored(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    (data / "a.txt").write_text("one")
    base = str(data / "base.json")
    run("init", str(data), "-b", base)
    assert run("check", "-b", base).returncode == 0


def test_missing_baseline_exits_2(tmp_path):
    result = run("check", "-b", str(tmp_path / "nope.json"))
    assert result.returncode == 2
    assert "[ERROR]" in result.stderr


def test_init_missing_path_exits_2(tmp_path):
    result = run("init", str(tmp_path / "nope"), "-b", str(tmp_path / "b.json"))
    assert result.returncode == 2


def test_exclude_pattern(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    (data / "a.txt").write_text("one")
    (data / "noise.log").write_text("x")
    base = str(tmp_path / "base.json")
    run("init", str(data), "-b", base, "-e", "*.log")
    (data / "noise.log").write_text("changed")
    assert run("check", "-b", base).returncode == 0
