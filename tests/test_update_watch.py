"""End-to-end tests for the update and watch commands."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run(*args, stdin=""):
    return subprocess.run([sys.executable, "-m", "integritywatch", *args],
                          cwd=ROOT, capture_output=True, text=True, input=stdin)


def make_baseline(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    (data / "a.txt").write_text("one")
    base = str(tmp_path / "base.json")
    run("init", str(data), "-b", base)
    return data, base


def test_update_with_yes_accepts_changes(tmp_path):
    data, base = make_baseline(tmp_path)
    (data / "a.txt").write_text("changed")
    assert run("check", "-b", base).returncode == 1
    assert run("update", "-b", base, "-y").returncode == 0
    assert run("check", "-b", base).returncode == 0


def test_update_prompt_yes(tmp_path):
    data, base = make_baseline(tmp_path)
    (data / "a.txt").write_text("changed")
    run("update", "-b", base, stdin="y\n")
    assert run("check", "-b", base).returncode == 0


def test_update_declined_keeps_baseline(tmp_path):
    data, base = make_baseline(tmp_path)
    (data / "a.txt").write_text("changed")
    result = run("update", "-b", base, stdin="n\n")
    assert "Aborted" in result.stdout
    assert run("check", "-b", base).returncode == 1


def test_update_without_input_is_safe(tmp_path):
    data, base = make_baseline(tmp_path)
    (data / "a.txt").write_text("changed")
    run("update", "-b", base)  # no -y and no input: must not change anything
    assert run("check", "-b", base).returncode == 1


def test_update_nothing_to_do(tmp_path):
    _data, base = make_baseline(tmp_path)
    result = run("update", "-b", base, "-y")
    assert "already up to date" in result.stdout


def test_watch_alerts_once_per_change(tmp_path):
    data, base = make_baseline(tmp_path)
    (data / "a.txt").write_text("changed")
    result = run("watch", "-b", base, "-i", "0.1", "-n", "3")
    assert result.returncode == 1
    assert result.stdout.count("ALERT") == 1   # not repeated every cycle


def test_watch_clean_exits_0(tmp_path):
    _data, base = make_baseline(tmp_path)
    result = run("watch", "-b", base, "-i", "0.1", "-n", "2")
    assert result.returncode == 0
    assert "ALERT" not in result.stdout


def test_watch_rejects_bad_interval(tmp_path):
    _data, base = make_baseline(tmp_path)
    assert run("watch", "-b", base, "-i", "0").returncode == 2


def test_watch_missing_baseline_exits_2(tmp_path):
    assert run("watch", "-b", str(tmp_path / "nope.json"), "-n", "1").returncode == 2
