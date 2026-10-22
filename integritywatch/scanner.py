"""Scanner: walk files and folders and collect metadata for each file."""

from __future__ import annotations

import fnmatch
import hashlib
import os
import stat
from collections.abc import Iterable, Sequence
from typing import Any

CHUNK_SIZE = 1024 * 1024  # read files 1 MB at a time so big files don't fill memory

# one file's metadata, and a whole snapshot (file path -> metadata)
Entry = dict[str, Any]
Entries = dict[str, Entry]


def hash_file(path: str) -> str:
    """Return the SHA-256 hex digest of a file's contents."""
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_excluded(path: str, patterns: Iterable[str]) -> bool:
    """Return True if the path (or just its name) matches any exclude pattern."""
    name = os.path.basename(path)
    return any(fnmatch.fnmatch(path, p) or fnmatch.fnmatch(name, p) for p in patterns)


def describe_file(path: str) -> Entry | None:
    """Return a metadata dict for one file, or None if it is not a file/symlink.

    Raises OSError if the file cannot be read (for example, permission denied).
    """
    info = os.lstat(path)  # lstat: do not follow symlinks

    if stat.S_ISLNK(info.st_mode):
        return {
            "type": "symlink",
            "target": os.readlink(path),
            "mode": stat.S_IMODE(info.st_mode),
            "uid": info.st_uid,
            "gid": info.st_gid,
        }

    if stat.S_ISREG(info.st_mode):
        return {
            "type": "file",
            "sha256": hash_file(path),
            "size": info.st_size,
            "mode": stat.S_IMODE(info.st_mode),
            "uid": info.st_uid,
            "gid": info.st_gid,
            "mtime": info.st_mtime,
        }

    return None  # sockets, devices, pipes, etc. are ignored


def scan_paths(
    paths: Iterable[str], excludes: Sequence[str] = ()
) -> tuple[Entries, list[str]]:
    """Scan files and folders. Return (entries, errors).

    entries: dict mapping absolute path -> metadata dict
    errors:  list of strings describing files/folders that could not be read
    """
    entries: Entries = {}
    errors: list[str] = []

    def record(path: str) -> None:
        try:
            data = describe_file(path)
        except OSError as err:
            errors.append(f"{path}: {err.strerror or err}")
            return
        if data is not None:
            entries[path] = data

    for top in paths:
        top = os.path.abspath(top)

        if not os.path.lexists(top):
            errors.append(f"{top}: no such file or directory")
            continue

        if not os.path.isdir(top) or os.path.islink(top):
            if not is_excluded(top, excludes):
                record(top)
            continue

        def on_walk_error(err: OSError) -> None:
            errors.append(f"{err.filename}: {err.strerror or err}")

        for root, dirs, files in os.walk(top, onerror=on_walk_error):
            # prune excluded folders so we never walk into them
            dirs[:] = [d for d in dirs if not is_excluded(os.path.join(root, d), excludes)]
            for name in files:
                full = os.path.join(root, name)
                if not is_excluded(full, excludes):
                    record(full)

    return entries, errors
