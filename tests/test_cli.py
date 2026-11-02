"""End-to-end tests: run ./render-schedule as a real process, exactly like a user would."""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "render-schedule"
SCHEDULE = str(ROOT / "examples" / "schedule.json")
OVERRIDES = str(ROOT / "examples" / "overrides.json")

# Copied verbatim from the brief.
BRIEF_OUTPUT = """\
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
"""


def run(*args: str, cwd: Path = ROOT) -> subprocess.CompletedProcess:
    return subprocess.run([str(SCRIPT), *args], capture_output=True, text=True, cwd=cwd)


def test_brief_example_output_matches_exactly():
    result = run(
        f"--schedule={SCHEDULE}",
        f"--overrides={OVERRIDES}",
        "--from=2026-11-06T17:00:00Z",
        "--until=2026-11-20T17:00:00Z",
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == BRIEF_OUTPUT
    assert result.stderr == ""


def test_works_when_run_from_another_directory(tmp_path):
    result = run(
        f"--schedule={SCHEDULE}",
        f"--overrides={OVERRIDES}",
        "--from=2026-11-06T17:00:00Z",
        "--until=2026-11-20T17:00:00Z",
        cwd=tmp_path,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == BRIEF_OUTPUT


def test_from_after_until_is_an_error():
    result = run(
        f"--schedule={SCHEDULE}",
        f"--overrides={OVERRIDES}",
        "--from=2026-11-20T17:00:00Z",
        "--until=2026-11-06T17:00:00Z",
    )
    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr == "error: --from must be before --until\n"


def test_missing_file_is_an_error(tmp_path):
    missing = tmp_path / "nope.json"
    result = run(
        f"--schedule={missing}",
        f"--overrides={OVERRIDES}",
        "--from=2026-11-06T17:00:00Z",
        "--until=2026-11-20T17:00:00Z",
    )
    assert result.returncode == 1
    assert result.stderr == f"error: {missing}: No such file or directory\n"


def test_invalid_json_is_an_error(tmp_path):
    broken = tmp_path / "broken.json"
    broken.write_text("{ not json")
    result = run(
        f"--schedule={SCHEDULE}",
        f"--overrides={broken}",
        "--from=2026-11-06T17:00:00Z",
        "--until=2026-11-20T17:00:00Z",
    )
    assert result.returncode == 1
    assert result.stderr.startswith(f"error: {broken}: invalid JSON")


def test_invalid_input_reports_where_the_problem_is():
    result = run(
        f"--schedule={SCHEDULE}",
        f"--overrides={OVERRIDES}",
        "--from=next tuesday",
        "--until=2026-11-20T17:00:00Z",
    )
    assert result.returncode == 1
    assert result.stderr == "error: --from: invalid timestamp 'next tuesday'\n"


def test_missing_flag_shows_usage():
    result = run(f"--schedule={SCHEDULE}")
    assert result.returncode == 2
    assert "usage: render-schedule" in result.stderr
    assert "required" in result.stderr
