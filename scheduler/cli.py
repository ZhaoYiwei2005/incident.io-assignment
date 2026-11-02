"""Command-line interface: read the input files, render the schedule, print it as JSON.

All I/O and error reporting lives here; the algorithm itself is in core.py.
"""

import argparse
import json
import sys
from typing import Any

from scheduler.core import render_schedule
from scheduler.models import InputError, Schedule, parse_overrides, parse_time


def main(argv: list[str] | None = None) -> int:
    """Run the CLI and return the process exit code (0 = success, 1 = bad input)."""
    args = _parse_args(argv)
    try:
        schedule = Schedule.from_json(_read_json(args.schedule))
        overrides = parse_overrides(_read_json(args.overrides))
        frm = parse_time(args.frm, "--from")
        until = parse_time(args.until, "--until")
        if frm >= until:
            raise InputError("--from must be before --until")
    except InputError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    entries = render_schedule(schedule, overrides, frm, until)
    print(json.dumps([entry.to_json() for entry in entries], indent=2))
    return 0


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    """Define and parse the command-line flags. Missing flags exit with code 2 (argparse)."""
    parser = argparse.ArgumentParser(
        prog="render-schedule",
        description="Render an on-call schedule, with overrides applied, as JSON.",
    )
    parser.add_argument("--schedule", required=True, metavar="FILE",
                        help="JSON file containing the schedule definition")
    parser.add_argument("--overrides", required=True, metavar="FILE",
                        help="JSON file containing an array of overrides")
    parser.add_argument("--from", dest="frm", required=True, metavar="TIME",
                        help="start of the window, e.g. 2026-11-06T17:00:00Z")
    parser.add_argument("--until", required=True, metavar="TIME",
                        help="end of the window, e.g. 2026-11-20T17:00:00Z")
    return parser.parse_args(argv)


def _read_json(path: str) -> Any:
    """Load a JSON file, turning file and syntax problems into InputError."""
    try:
        with open(path, encoding="utf-8") as file:
            return json.load(file)
    except OSError as error:
        raise InputError(f"{path}: {error.strerror}") from None
    except json.JSONDecodeError as error:
        raise InputError(f"{path}: invalid JSON ({error})") from None
