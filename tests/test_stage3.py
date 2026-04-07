from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from typer.testing import CliRunner

from convdrift.cli import app, run_analysis_loop
from convdrift.config import Config
from convdrift.history import list_session_summaries
from convdrift.store import ScoreStore, build_session_id


FIXTURES_DIR = Path(__file__).parent / "fixtures"
GOOD_FIXTURE_PATH = FIXTURES_DIR / "stage1_good_transcript.jsonl"


def test_run_writes_session_timeline_and_commands_can_read_it(tmp_path: Path) -> None:
    runner = CliRunner()
    store_path = tmp_path / "scores.sqlite3"
    sessions_dir = tmp_path / "sessions"

    result = runner.invoke(
        app,
        [
            "run",
            str(GOOD_FIXTURE_PATH),
            "--store-path",
            str(store_path),
            "--sessions-dir",
            str(sessions_dir),
        ],
    )

    assert result.exit_code == 0

    session_id = build_session_id(GOOD_FIXTURE_PATH)
    log_result = runner.invoke(
        app,
        ["log", session_id, "--sessions-dir", str(sessions_dir)],
    )
    sessions_result = runner.invoke(
        app,
        ["sessions", "--sessions-dir", str(sessions_dir)],
    )

    assert log_result.exit_code == 0
    assert "episode=1" in log_result.stdout
    assert "episode=3" in log_result.stdout
    assert sessions_result.exit_code == 0
    assert session_id in sessions_result.stdout


def test_statusline_reads_score_store(tmp_path: Path) -> None:
    runner = CliRunner()
    store_path = tmp_path / "scores.sqlite3"
    sessions_dir = tmp_path / "sessions"

    run_result = runner.invoke(
        app,
        [
            "run",
            str(GOOD_FIXTURE_PATH),
            "--store-path",
            str(store_path),
            "--sessions-dir",
            str(sessions_dir),
        ],
    )
    assert run_result.exit_code == 0

    result = runner.invoke(
        app,
        [
            "statusline",
            str(store_path),
            "--transcript",
            str(GOOD_FIXTURE_PATH),
            "--output-format",
            "with-metrics",
        ],
    )

    assert result.exit_code == 0
    assert "D:" in result.stdout
    assert "[err:" in result.stdout


def test_statusline_run_with_valid_stdin_runs_analysis_and_prints_indicator(
    tmp_path: Path,
) -> None:
    runner = CliRunner()
    store_path = tmp_path / "statusline.sqlite3"
    sessions_dir = tmp_path / "sessions"

    result = runner.invoke(
        app,
        [
            "statusline-run",
            "--store-path",
            str(store_path),
            "--sessions-dir",
            str(sessions_dir),
        ],
        input=json.dumps({"transcript_path": str(GOOD_FIXTURE_PATH)}),
    )

    assert result.exit_code == 0
    assert "D:" in result.stdout
    assert store_path.exists()
    latest = ScoreStore(store_path).fetch_latest_snapshot(
        transcript_path=GOOD_FIXTURE_PATH
    )
    assert latest is not None


def test_statusline_run_with_missing_transcript_path_exits_cleanly() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["statusline-run"], input=json.dumps({}))

    assert result.exit_code == 0
    assert result.stdout == ""


def test_follow_loop_processes_growing_transcript_end_to_end(tmp_path: Path) -> None:
    transcript_path = tmp_path / "live.jsonl"
    store = ScoreStore(tmp_path / "live.sqlite3")
    store.initialize()
    sessions_dir = tmp_path / "sessions"
    config = Config()

    source_lines = GOOD_FIXTURE_PATH.read_text(encoding="utf-8").splitlines()
    transcript_path.write_text("\n".join(source_lines[:4]) + "\n", encoding="utf-8")

    emitted: list[str] = []

    thread = threading.Thread(
        target=run_analysis_loop,
        kwargs={
            "transcript": transcript_path,
            "score_store": store,
            "config": config,
            "output_format": "score-only",
            "follow": True,
            "sessions_dir": sessions_dir,
            "emitter": emitted.append,
            "max_updates": 2,
        },
        daemon=True,
    )
    thread.start()
    time.sleep(0.2)
    with transcript_path.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(source_lines[4:]) + "\n")
    thread.join(timeout=5)

    assert not thread.is_alive()
    latest = store.fetch_latest_snapshot(transcript_path=transcript_path)
    assert latest is not None
    assert latest["episode_count"] == 3
    assert len(emitted) == 2
    summaries = list_session_summaries(sessions_dir)
    assert len(summaries) == 1
