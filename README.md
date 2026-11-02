# render-schedule

A command-line tool that renders an on-call schedule. It projects a rotation of users, applies
overrides on top, and truncates the result to a time window. This is my solution to the incident.io 
take-home; the original brief is in [TASK.md](TASK.md).

## Requirements

- **Python 3.11 or newer.** Check with `python3 --version`.
- **No dependencies to run it.** It uses only the Python standard library.
- **pytest, only to run the tests** (see below).

## Running it

From the project root:

```console
$ ./render-schedule \
    --schedule=examples/schedule.json \
    --overrides=examples/overrides.json \
    --from='2026-11-06T17:00:00Z' \
    --until='2026-11-20T17:00:00Z'
[
  {
    "user": "alice",
    "start_at": "2026-11-06T17:00:00Z",
    "end_at": "2026-11-09T17:00:00Z"
  },
  {
    "user": "charlie",
    "start_at": "2026-11-09T17:00:00Z",
    "end_at": "2026-11-09T22:00:00Z"
  },
  {
    "user": "alice",
    "start_at": "2026-11-09T22:00:00Z",
    "end_at": "2026-11-13T17:00:00Z"
  },
  {
    "user": "bob",
    "start_at": "2026-11-13T17:00:00Z",
    "end_at": "2026-11-20T17:00:00Z"
  }
]
```

`examples/` contains the schedule and overrides from the brief. Run `./render-schedule --help` to see all the flags.

If the script isn't executable (some ZIP tools drop the permission), run it as `python3 render-schedule ...`.

**Exit codes:**

| Code | Meaning |
|---|---|
| `0` | success; JSON is printed to stdout |
| `1` | invalid input (missing file, bad JSON, invalid timestamp, `--from` not before `--until`, ...); an `error: ...` message is printed to stderr |
| `2` | missing or unknown flags; the usage message is printed |

## Running the tests

```console
$ python3 -m venv .venv && source .venv/bin/activate   # optional
$ pip install -r requirements-dev.txt
$ pytest
```

There are four test files:

- **`tests/test_core.py`** tests each step of the algorithm in isolation, plus edge cases through the whole
  pipeline, with the brief's example as a golden test.
- **`tests/test_models.py`** tests timestamp parsing and formatting, and input validation.
- **`tests/test_cli.py`** runs the real `./render-schedule` executable and compares its output with the brief's
  output character for character. It also checks the error paths.
- **`tests/test_invariants.py`** runs 200 seeded random schedules, overrides and windows. For each one it
  checks that the output is sorted, has no overlaps, stays within the window, has its same-user neighbours
  merged, and agrees with an independent "who is on call at instant *t*?" check at every boundary.

## How it works

The algorithm in `scheduler/core.py` is a pipeline of four small, pure functions. Each one takes and returns a
list of entries:

```python
shifts   = rotation_shifts(schedule, frm, until)   # 1. project the rotation
timeline = overlay(base=shifts, top=overrides)      # 2. overrides win where they apply
timeline = clip(timeline, frm, until)               # 3. truncate to the window
return merge_adjacent(timeline)                     # 4. join same-user neighbours
```

1. **`rotation_shifts`** generates the rotation's shifts that overlap the window. The shift containing an
   instant is `(t - handover_start) // interval`, and `% len(users)` picks whose turn it is.
2. **`overlay`** is the core idea. The on-call person can only change at a point where some shift or override
   starts or ends. So the function sorts all of those points, and for each segment between two consecutive
   points it asks one question: *does an override cover this segment? If not, whose shift is it?* This
   replaces hand-written "split a shift around an override" logic. Overrides that cross a handover or overlap
   the window edges need no special cases.
3. **`clip`** trims entries to `[from, until)` and drops any that fall outside the window.
4. **`merge_adjacent`** joins back-to-back entries for the same user, for example when someone overrides
   their own shift.

Every entry is a **half-open interval `[start, end)`**: it includes its start but not its end. That way,
back-to-back entries never overlap, and a handover instant belongs to exactly one person.

`overlay` is roughly O(points × entries). The brief prioritises correctness over performance for windows of a
few weeks and fewer than 100 overrides, so that cost is irrelevant here. Sorting the overrides and scanning
them in order would make it linear if needed.

## Project layout

```
render-schedule          executable entry point (checks the Python version, then calls scheduler.cli.main)
scheduler/
  cli.py                 flags, file reading, JSON output, error messages and exit codes
  core.py                the scheduling algorithm (pure functions, no I/O)
  models.py              Entry and Schedule types; JSON and timestamp parsing with validation
tests/                   unit, edge-case, end-to-end and randomised invariant tests
examples/                the schedule and overrides from the brief
TASK.md                  the original brief
```

Dependencies only go one way, `cli → core → models`. The algorithm never touches files or raw JSON, which keeps
it easy to test and to reuse, for example behind an HTTP API.
