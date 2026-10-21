"""Tests for how scan warnings are shown."""

import subprocess
import sys
from pathlib import Path

from integritywatch.cli import format_warnings

ROOT = Path(__file__).resolve().parent.parent


def run(*args):
    return subprocess.run([sys.executable, "-m", "integritywatch", *args],
                          cwd=ROOT, capture_output=True, text=True, input="")


def test_no_errors_gives_no_warnings():
    assert format_warnings([], verbose=False) == []


def test_few_errors_are_all_shown():
    errors = ["/a: Permission denied", "/b: Permission denied"]
    assert format_warnings(errors, verbose=False) == [f"[WARNING] {e}" for e in errors]


def test_many_errors_are_summarized():
    errors = [f"/f{i}: Permission denied" for i in range(10)]
    lines = format_warnings(errors, verbose=False)
    assert len(lines) == 4
    assert lines[0] == "[WARNING] /f0: Permission denied"
    assert "7 more" in lines[-1]
    assert "--verbose" in lines[-1]


def test_verbose_shows_everything():
    errors = [f"/f{i}: Permission denied" for i in range(10)]
    assert len(format_warnings(errors, verbose=True)) == 10


def test_verbose_flag_is_accepted(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    (data / "a.txt").write_text("x")
    base = str(tmp_path / "b.json")
    assert run("init", str(data), "-b", base, "-v").returncode == 0
    assert run("check", "-b", base, "--verbose").returncode == 0
