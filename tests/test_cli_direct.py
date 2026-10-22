"""Tests that call main() directly, so coverage tools can see the CLI code run.

The other CLI tests start the tool as a separate process. That is the most
realistic test, but coverage tools cannot measure code inside a child process.
"""

import io
import json
import os
import runpy
import sys
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

from integritywatch import scanner
from integritywatch.baseline import load_baseline
from integritywatch.cli import main


def run_main(*args, stdin=""):
    """Run main() with captured output. Return (exit_code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with mock.patch("sys.stdin", io.StringIO(stdin)):
        with redirect_stdout(out), redirect_stderr(err):
            code = main(list(args))
    return code, out.getvalue(), err.getvalue()


def make_baseline(tmp_path):
    """Create a small folder and a baseline for it. Return (folder, baseline_path)."""
    data = tmp_path / "data"
    data.mkdir()
    (data / "a.txt").write_text("one")
    base = str(tmp_path / "base.json")
    code, _out, _err = run_main("init", str(data), "-b", base)
    assert code == 0
    return data, base


def test_no_command_prints_help_and_returns_2():
    code, out, _err = run_main()
    assert code == 2
    assert "usage:" in out


def test_version_flag_exits_zero():
    out = io.StringIO()
    try:
        with redirect_stdout(out):
            main(["--version"])
    except SystemExit as exit_info:
        assert exit_info.code == 0
    else:
        raise AssertionError("--version should exit")
    assert "integritywatch" in out.getvalue()


def test_module_entry_point_runs():
    out = io.StringIO()
    try:
        with mock.patch.object(sys, "argv", ["integritywatch", "--version"]):
            with redirect_stdout(out):
                runpy.run_module("integritywatch", run_name="__main__")
    except SystemExit as exit_info:
        assert exit_info.code == 0
    else:
        raise AssertionError("module entry point should exit")


def test_init_reports_files_recorded(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    (data / "a.txt").write_text("one")
    code, out, _err = run_main("init", str(data), "-b", str(tmp_path / "b.json"))
    assert code == 0
    assert "Files recorded: 1" in out


def test_init_skips_missing_path_with_warning(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    (data / "a.txt").write_text("one")
    missing = str(tmp_path / "missing")
    code, out, err = run_main("init", str(data), missing, "-b", str(tmp_path / "b.json"))
    assert code == 0
    assert "Skipped (unreadable): 1" in out
    assert "[WARNING]" in err


def test_init_with_nothing_to_record_fails(tmp_path):
    code, _out, err = run_main("init", str(tmp_path / "nope"), "-b", str(tmp_path / "b.json"))
    assert code == 2
    assert "no files found" in err


def test_init_unwritable_baseline_fails_cleanly(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    (data / "a.txt").write_text("one")
    bad_baseline = str(tmp_path / "no_such_folder" / "b.json")
    code, _out, err = run_main("init", str(data), "-b", bad_baseline)
    assert code == 2
    assert "cannot write baseline" in err


def test_warnings_are_summarized_unless_verbose(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    (data / "a.txt").write_text("one")
    missing = [str(tmp_path / f"missing{i}") for i in range(5)]
    base = str(tmp_path / "b.json")

    _code, _out, err = run_main("init", str(data), *missing, "-b", base)
    assert "2 more not shown" in err

    _code, _out, err = run_main("init", str(data), *missing, "-b", base, "-v")
    assert "more not shown" not in err
    assert err.count("[WARNING]") == 5


def test_check_clean(tmp_path):
    _data, base = make_baseline(tmp_path)
    code, out, _err = run_main("check", "-b", base)
    assert code == 0
    assert "No changes" in out


def test_check_quiet_prints_nothing_when_clean(tmp_path):
    _data, base = make_baseline(tmp_path)
    code, out, _err = run_main("check", "-b", base, "-q")
    assert code == 0
    assert out == ""


def test_check_reports_every_kind_of_change(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    (data / "a.txt").write_text("one")
    (data / "b.txt").write_text("two")
    os.chmod(data / "a.txt", 0o644)  # known starting permissions, so chmod below is a real change
    base = str(tmp_path / "base.json")
    run_main("init", str(data), "-b", base)

    (data / "a.txt").write_text("changed")
    os.chmod(data / "a.txt", 0o600)
    (data / "b.txt").unlink()
    (data / "c.txt").write_text("new")

    code, out, _err = run_main("check", "-b", base)
    assert code == 1
    for label in ("[MODIFIED]", "[PERMISSIONS]", "[DELETED]", "[NEW]"):
        assert label in out


def test_check_json_output(tmp_path):
    data, base = make_baseline(tmp_path)
    (data / "a.txt").write_text("two")
    code, out, _err = run_main("check", "-b", base, "-f", "json")
    report = json.loads(out)
    assert code == 1
    assert report["total_changes"] == 1
    assert report["changes"]["modified"][0]["path"].endswith("a.txt")


def test_check_missing_baseline_returns_2(tmp_path):
    code, _out, err = run_main("check", "-b", str(tmp_path / "nope.json"))
    assert code == 2
    assert "[ERROR]" in err


def test_check_warns_when_monitored_folder_disappears(tmp_path):
    data, base = make_baseline(tmp_path)
    (data / "a.txt").unlink()
    data.rmdir()
    code, out, err = run_main("check", "-b", base)
    assert code == 1
    assert "[DELETED]" in out
    assert "[WARNING]" in err


def test_update_yes_accepts_changes(tmp_path):
    data, base = make_baseline(tmp_path)
    (data / "a.txt").write_text("changed")
    code, out, _err = run_main("update", "-b", base, "-y")
    assert code == 0
    assert "Baseline updated" in out
    assert run_main("check", "-b", base)[0] == 0


def test_update_prompt_accepts_y(tmp_path):
    data, base = make_baseline(tmp_path)
    (data / "a.txt").write_text("changed")
    code, out, _err = run_main("update", "-b", base, stdin="y\n")
    assert code == 0
    assert "[y/N]" in out
    assert run_main("check", "-b", base)[0] == 0


def test_update_prompt_declined_keeps_baseline(tmp_path):
    data, base = make_baseline(tmp_path)
    (data / "a.txt").write_text("changed")
    _code, out, _err = run_main("update", "-b", base, stdin="n\n")
    assert "Aborted" in out
    assert run_main("check", "-b", base)[0] == 1


def test_update_without_any_input_changes_nothing(tmp_path):
    data, base = make_baseline(tmp_path)
    (data / "a.txt").write_text("changed")
    _code, out, _err = run_main("update", "-b", base, stdin="")
    assert "Aborted" in out
    assert run_main("check", "-b", base)[0] == 1


def test_update_with_nothing_to_accept(tmp_path):
    _data, base = make_baseline(tmp_path)
    code, out, _err = run_main("update", "-b", base, "-y")
    assert code == 0
    assert "already up to date" in out


def test_watch_alerts_once_for_a_lasting_change(tmp_path):
    data, base = make_baseline(tmp_path)
    (data / "a.txt").write_text("changed")
    with mock.patch("integritywatch.cli.time.sleep"):
        code, out, _err = run_main("watch", "-b", base, "-i", "1", "-n", "3")
    assert code == 1
    assert out.count("ALERT") == 1


def test_watch_reports_when_files_match_again(tmp_path):
    data, base = make_baseline(tmp_path)
    (data / "a.txt").write_text("changed")

    def undo_change(_seconds):
        (data / "a.txt").write_text("one")

    with mock.patch("integritywatch.cli.time.sleep", undo_change):
        code, out, _err = run_main("watch", "-b", base, "-i", "1", "-n", "2")
    assert code == 0
    assert "ALERT" in out
    assert "match the baseline again" in out


def test_watch_stops_cleanly_on_ctrl_c(tmp_path):
    _data, base = make_baseline(tmp_path)
    with mock.patch("integritywatch.cli.time.sleep", side_effect=KeyboardInterrupt):
        code, out, _err = run_main("watch", "-b", base, "-i", "1")
    assert code == 0
    assert "Stopped" in out


def test_watch_rejects_bad_interval(tmp_path):
    _data, base = make_baseline(tmp_path)
    code, _out, err = run_main("watch", "-b", base, "-i", "0")
    assert code == 2
    assert "--interval" in err


def test_watch_missing_baseline_returns_2(tmp_path):
    code, _out, _err = run_main("watch", "-b", str(tmp_path / "nope.json"), "-n", "1")
    assert code == 2


def test_update_keeps_old_record_of_files_that_became_unreadable(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    (data / "a.txt").write_text("one")
    (data / "b.txt").write_text("two")
    base = str(tmp_path / "base.json")
    run_main("init", str(data), "-b", base)

    (data / "a.txt").write_text("changed")
    locked = str(data / "b.txt")
    real_hash = scanner.hash_file

    def hash_unless_locked(path):
        if path == locked:
            raise PermissionError(13, "Permission denied")
        return real_hash(path)

    with mock.patch("integritywatch.scanner.hash_file", hash_unless_locked):
        code, out, err = run_main("check", "-b", base)
        assert code == 1
        assert "[DELETED]" not in out  # an unreadable file is not a deleted file
        assert "Permission denied" in err
        run_main("update", "-b", base, "-y")

    assert locked in load_baseline(base)["files"]
