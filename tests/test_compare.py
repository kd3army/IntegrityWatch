from integritywatch.compare import compare, total_changes


def file_entry(sha="aaa", mode=0o644, uid=1000, gid=1000):
    return {"type": "file", "sha256": sha, "size": 1, "mode": mode,
            "uid": uid, "gid": gid, "mtime": 0}


def test_no_changes():
    snap = {"/a": file_entry()}
    assert total_changes(compare(snap, dict(snap))) == 0


def test_modified_content():
    changes = compare({"/a": file_entry("aaa")}, {"/a": file_entry("bbb")})
    assert [c["path"] for c in changes["modified"]] == ["/a"]


def test_permission_change():
    changes = compare({"/a": file_entry(mode=0o644)}, {"/a": file_entry(mode=0o666)})
    assert changes["permissions"][0]["detail"] == "0644 -> 0666"
    assert changes["modified"] == []


def test_owner_change():
    changes = compare({"/a": file_entry(uid=1000)}, {"/a": file_entry(uid=0)})
    assert len(changes["owner"]) == 1


def test_deleted_and_new():
    changes = compare({"/old": file_entry()}, {"/new": file_entry()})
    assert changes["deleted"][0]["path"] == "/old"
    assert changes["new"][0]["path"] == "/new"


def test_unreadable_file_is_not_reported_deleted():
    changes = compare({"/secret": file_entry()}, {}, unreadable={"/secret"})
    assert changes["deleted"] == []


def test_symlink_target_change():
    old = {"/l": {"type": "symlink", "target": "/x", "mode": 0o777, "uid": 0, "gid": 0}}
    new = {"/l": {"type": "symlink", "target": "/y", "mode": 0o777, "uid": 0, "gid": 0}}
    assert len(compare(old, new)["modified"]) == 1


def test_type_change_is_modified():
    old = {"/a": file_entry()}
    new = {"/a": {"type": "symlink", "target": "/x", "mode": 0o777, "uid": 1000, "gid": 1000}}
    assert "type changed" in compare(old, new)["modified"][0]["detail"]
