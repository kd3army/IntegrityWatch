import os
import stat

from integritywatch.scanner import hash_file, is_excluded, scan_paths


def test_hash_file_known_value(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("hello")
    # SHA-256 of the text "hello"
    assert hash_file(str(f)) == (
        "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
    )


def test_scan_collects_metadata(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("hello")
    entries, errors = scan_paths([str(tmp_path)])
    assert errors == []
    entry = entries[str(f)]
    assert entry["type"] == "file"
    assert entry["size"] == 5
    assert entry["mode"] == stat.S_IMODE(os.stat(f).st_mode)


def test_scan_walks_subfolders(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.txt").write_text("x")
    entries, _ = scan_paths([str(tmp_path)])
    assert str(tmp_path / "sub" / "b.txt") in entries


def test_exclude_by_name_and_folder(tmp_path):
    (tmp_path / "keep.txt").write_text("1")
    (tmp_path / "skip.log").write_text("2")
    (tmp_path / "cache").mkdir()
    (tmp_path / "cache" / "c.txt").write_text("3")
    entries, _ = scan_paths([str(tmp_path)], excludes=["*.log", "cache"])
    names = {os.path.basename(p) for p in entries}
    assert names == {"keep.txt"}


def test_symlink_is_recorded_not_followed(tmp_path):
    target = tmp_path / "real.txt"
    target.write_text("data")
    link = tmp_path / "link.txt"
    link.symlink_to(target)
    entries, _ = scan_paths([str(tmp_path)])
    assert entries[str(link)]["type"] == "symlink"
    assert entries[str(link)]["target"] == str(target)


def test_missing_path_reports_error(tmp_path):
    entries, errors = scan_paths([str(tmp_path / "nope")])
    assert entries == {}
    assert len(errors) == 1


def test_is_excluded_patterns():
    assert is_excluded("/var/log/syslog.log", ["*.log"])
    assert not is_excluded("/etc/passwd", ["*.log"])
