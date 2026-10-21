"""Baseline storage: save and load the snapshot of file metadata as JSON."""

import datetime
import json
import os

BASELINE_VERSION = 1


class BaselineError(Exception):
    """Raised when a baseline cannot be written, read or understood."""


def save_baseline(path, entries, paths, excludes):
    """Write the baseline to `path` as JSON.

    entries:  dict of file path -> metadata (from scanner.scan_paths)
    paths:    the folders/files that were scanned
    excludes: the exclude patterns that were used
    """
    data = {
        "version": BASELINE_VERSION,
        "created": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "paths": list(paths),
        "excludes": list(excludes),
        "files": entries,
    }
    tmp = path + ".tmp"
    try:
        # 0600: the baseline lists your files, so only the owner may read it
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2, sort_keys=True)
        os.replace(tmp, path)  # atomic: a crash never leaves a half-written baseline
    except OSError as err:
        raise BaselineError(f"cannot write baseline {path}: {err.strerror or err}")


def load_baseline(path):
    """Read and validate a baseline file. Return it as a dict."""
    try:
        with open(path) as f:
            data = json.load(f)
    except FileNotFoundError:
        raise BaselineError(f"baseline not found: {path} (run 'init' first)")
    except PermissionError:
        raise BaselineError(f"no permission to read baseline: {path}")
    except json.JSONDecodeError:
        raise BaselineError(f"baseline is not valid JSON: {path}")

    if not isinstance(data, dict) or data.get("version") != BASELINE_VERSION:
        raise BaselineError(f"unsupported baseline format: {path}")
    for key in ("paths", "excludes", "files"):
        if key not in data:
            raise BaselineError(f"baseline is missing '{key}': {path}")
    return data
