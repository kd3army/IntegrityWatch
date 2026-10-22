"""Command-line interface for IntegrityWatch.

Exit codes:  0 = no changes   1 = changes detected   2 = error
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
import time
from collections.abc import Sequence
from typing import Any

from . import __version__
from .baseline import BaselineError, load_baseline, save_baseline
from .compare import Changes, compare, total_changes
from .scanner import Entries, scan_paths

DEFAULT_BASELINE = "baseline.json"

LABELS = {
    "modified": "[MODIFIED]   ",
    "permissions": "[PERMISSIONS]",
    "owner": "[OWNER]      ",
    "deleted": "[DELETED]    ",
    "new": "[NEW]        ",
}

MAX_WARNINGS = 3  # warnings shown by default before the rest are summarized


def format_warnings(errors: Sequence[str], verbose: bool = False) -> list[str]:
    """Return warning lines. Long lists are shortened unless verbose is True."""
    lines = [f"[WARNING] {err}" for err in errors]
    if verbose or len(lines) <= MAX_WARNINGS:
        return lines
    hidden = len(lines) - MAX_WARNINGS
    return lines[:MAX_WARNINGS] + [
        f"[WARNING] ... and {hidden} more not shown (use --verbose to list all)"
    ]


def print_warnings(errors: Sequence[str], verbose: bool = False) -> None:
    """Print scan warnings to stderr."""
    for line in format_warnings(errors, verbose):
        print(line, file=sys.stderr)


def cmd_init(args: argparse.Namespace) -> int:
    """Scan the given paths and save a new baseline."""
    # never include the baseline file itself in the scan
    excludes = list(args.exclude) + [os.path.abspath(args.baseline)]
    paths = [os.path.abspath(p) for p in args.paths]

    entries, errors = scan_paths(paths, excludes)
    print_warnings(errors, args.verbose)

    if not entries:
        print("[ERROR] no files found to record", file=sys.stderr)
        return 2

    save_baseline(args.baseline, entries, paths, args.exclude)
    print(f"[OK] Baseline saved to {args.baseline}")
    print(f"     Files recorded: {len(entries)}")
    if errors:
        print(f"     Skipped (unreadable): {len(errors)}")
    return 0


def scan_and_compare(
    data: dict[str, Any], baseline_path: str
) -> tuple[Entries, Changes, list[str], set[str]]:
    """Scan the monitored paths and compare with the baseline.

    Returns (entries, changes, errors, unreadable).
    """
    excludes = data["excludes"] + [os.path.abspath(baseline_path)]
    entries, errors = scan_paths(data["paths"], excludes)

    # files we could not read now are not "deleted", they are just unreadable
    unreadable = {p for p in data["files"] if any(e.startswith(p + ": ") for e in errors)}
    changes = compare(data["files"], entries, unreadable)
    return entries, changes, errors, unreadable


def cmd_check(args: argparse.Namespace) -> int:
    """Compare the current state against the saved baseline."""
    data = load_baseline(args.baseline)
    _entries, changes, errors, _unreadable = scan_and_compare(data, args.baseline)
    print_warnings(errors, args.verbose)
    count = total_changes(changes)

    if args.format == "json":
        print(json.dumps({"baseline": args.baseline, "total_changes": count,
                          "changes": changes}, indent=2))
    elif count or not args.quiet:
        print_text_report(args.baseline, data, changes, count)

    return 1 if count else 0


def cmd_update(args: argparse.Namespace) -> int:
    """Accept the current state of the files as the new baseline."""
    data = load_baseline(args.baseline)
    entries, changes, errors, unreadable = scan_and_compare(data, args.baseline)
    print_warnings(errors, args.verbose)
    count = total_changes(changes)

    if count == 0:
        print("[OK] Baseline is already up to date. Nothing to accept.")
        return 0

    print_text_report(args.baseline, data, changes, count)

    if not args.yes:
        try:
            print(f"Accept these {count} change(s) as the new baseline? [y/N] ", end="", flush=True)
            answer = input()
        except EOFError:
            answer = ""
        if answer.strip().lower() not in ("y", "yes"):
            print("Aborted. Baseline unchanged.")
            return 0

    # keep the old record of files we could not read, so they are not lost
    for path in unreadable:
        entries[path] = data["files"][path]

    save_baseline(args.baseline, entries, data["paths"], data["excludes"])
    print(f"[OK] Baseline updated. {count} change(s) accepted.")
    return 0


def cmd_watch(args: argparse.Namespace) -> int:
    """Check repeatedly and alert when something changes."""
    if args.interval <= 0:
        print("[ERROR] --interval must be greater than 0", file=sys.stderr)
        return 2

    data = load_baseline(args.baseline)
    print(f"[*] Watching {len(data['files'])} files every {args.interval:g}s. "
          "Press Ctrl+C to stop.")

    last_alert: str | None = None  # remember the last alert so we do not repeat it
    checks = 0
    try:
        while True:
            _entries, changes, errors, _unreadable = scan_and_compare(data, args.baseline)
            if checks == 0:
                print_warnings(errors, args.verbose)
            count = total_changes(changes)
            signature = json.dumps(changes, sort_keys=True)
            now = datetime.datetime.now().strftime("%H:%M:%S")

            if count and signature != last_alert:
                print(f"[{now}] ALERT: {count} change(s) detected")
                print_text_report(args.baseline, data, changes, count)
                last_alert = signature
            elif not count and last_alert is not None:
                print(f"[{now}] OK: files match the baseline again")
                last_alert = None

            checks += 1
            if args.count and checks >= args.count:
                break
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\n[*] Stopped.")

    return 1 if last_alert is not None else 0


def print_text_report(
    baseline_path: str, data: dict[str, Any], changes: Changes, count: int
) -> None:
    """Print a human-readable report of the changes."""
    print("=" * 46)
    print(" INTEGRITYWATCH CHECK")
    print(f" Baseline: {baseline_path}")
    print(f" Created : {data['created']}  ({len(data['files'])} files)")
    print("=" * 46)
    for category, items in changes.items():
        for item in items:
            detail = f"  ({item['detail']})" if "detail" in item else ""
            print(f"{LABELS[category]} {item['path']}{detail}")
    print("-" * 46)
    summary = "  ".join(f"{name.capitalize()}: {len(items)}" for name, items in changes.items())
    print(summary)
    if count:
        print("[WARNING] Changes detected!")
    else:
        print("[OK] No changes. All files match the baseline.")


def build_parser() -> argparse.ArgumentParser:
    """Create the argument parser with its subcommands."""
    parser = argparse.ArgumentParser(
        prog="integritywatch",
        description="IntegrityWatch - detect unauthorized changes to files.",
        epilog="Example: integritywatch init /etc/ssh && integritywatch check",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command")

    init = sub.add_parser("init", help="scan paths and create a baseline")
    init.add_argument("paths", nargs="+", help="files or folders to monitor")
    init.add_argument("-b", "--baseline", default=DEFAULT_BASELINE,
                      help=f"baseline file (default {DEFAULT_BASELINE})")
    init.add_argument("-e", "--exclude", action="append", default=[], metavar="PATTERN",
                      help="skip files/folders matching this pattern (repeatable), e.g. '*.log'")
    init.set_defaults(func=cmd_init)

    check = sub.add_parser("check", help="compare current state with the baseline")
    check.add_argument("-b", "--baseline", default=DEFAULT_BASELINE,
                       help=f"baseline file (default {DEFAULT_BASELINE})")
    check.add_argument("-f", "--format", choices=["text", "json"], default="text",
                       help="output format (default text)")
    check.add_argument("-q", "--quiet", action="store_true",
                       help="print nothing when there are no changes (good for cron)")
    check.set_defaults(func=cmd_check)

    update = sub.add_parser("update", help="accept current changes as the new baseline")
    update.add_argument("-b", "--baseline", default=DEFAULT_BASELINE,
                        help=f"baseline file (default {DEFAULT_BASELINE})")
    update.add_argument("-y", "--yes", action="store_true",
                        help="do not ask for confirmation")
    update.set_defaults(func=cmd_update)

    watch = sub.add_parser("watch", help="check repeatedly and alert on changes")
    watch.add_argument("-b", "--baseline", default=DEFAULT_BASELINE,
                       help=f"baseline file (default {DEFAULT_BASELINE})")
    watch.add_argument("-i", "--interval", type=float, default=30,
                       help="seconds between checks (default 30)")
    watch.add_argument("-n", "--count", type=int, default=0,
                       help="stop after this many checks (default: run until Ctrl+C)")
    watch.set_defaults(func=cmd_watch)
    for command in (init, check, update, watch):
        command.add_argument("-v", "--verbose", action="store_true",
                             help="list every unreadable file instead of a short summary")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return an exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 2
    try:
        return args.func(args)
    except BaselineError as err:
        print(f"[ERROR] {err}", file=sys.stderr)
        return 2
