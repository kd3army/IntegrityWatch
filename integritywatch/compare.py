"""Compare two snapshots (baseline vs. current) and describe what changed."""

CATEGORIES = ("modified", "permissions", "owner", "deleted", "new")


def _mode(value):
    """Format a numeric permission mode like 0644."""
    return f"{value:04o}"


def compare(old, new, unreadable=()):
    """Return a dict of change lists: modified, permissions, owner, deleted, new.

    old, new:   dicts of path -> metadata
    unreadable: paths that could not be read now; they are not reported as deleted
    """
    changes = {name: [] for name in CATEGORIES}

    for path in sorted(old):
        if path not in new:
            if path not in unreadable:
                changes["deleted"].append({"path": path})
            continue

        before, after = old[path], new[path]

        if before.get("type") != after.get("type"):
            changes["modified"].append({
                "path": path,
                "detail": f"type changed: {before.get('type')} -> {after.get('type')}",
            })
            continue

        if after["type"] == "file" and before.get("sha256") != after.get("sha256"):
            changes["modified"].append({"path": path, "detail": "content changed"})
        elif after["type"] == "symlink" and before.get("target") != after.get("target"):
            changes["modified"].append({
                "path": path,
                "detail": f"link target: {before.get('target')} -> {after.get('target')}",
            })

        if before.get("mode") != after.get("mode"):
            changes["permissions"].append({
                "path": path,
                "detail": f"{_mode(before['mode'])} -> {_mode(after['mode'])}",
            })

        if (before.get("uid"), before.get("gid")) != (after.get("uid"), after.get("gid")):
            changes["owner"].append({
                "path": path,
                "detail": (f"{before.get('uid')}:{before.get('gid')} -> "
                           f"{after.get('uid')}:{after.get('gid')}"),
            })

    for path in sorted(new):
        if path not in old:
            changes["new"].append({"path": path})

    return changes


def total_changes(changes):
    """Return the total number of changes across all categories."""
    return sum(len(items) for items in changes.values())
