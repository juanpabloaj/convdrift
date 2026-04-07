from pathlib import Path

from typer.testing import CliRunner

from convdrift.cli import app
from convdrift.config import Config
from convdrift.parser import load_messages
from convdrift.scoring import build_score_snapshots, latest_score_snapshot
from convdrift.segmenter import segment_messages
from convdrift.store import ScoreStore


FIXTURES_DIR = Path(__file__).parent / "fixtures"
GOOD_FIXTURE_PATH = FIXTURES_DIR / "stage1_good_transcript.jsonl"
BAD_FIXTURE_PATH = FIXTURES_DIR / "stage1_bad_transcript.jsonl"
CONFIG = Config()


def test_known_bad_transcript_scores_higher_than_known_good_transcript() -> None:
    good_episodes = segment_messages(load_messages(GOOD_FIXTURE_PATH))["main"]
    bad_episodes = segment_messages(load_messages(BAD_FIXTURE_PATH))["main"]

    good_snapshot = latest_score_snapshot(good_episodes, config=CONFIG)
    bad_snapshot = latest_score_snapshot(bad_episodes, config=CONFIG)

    assert good_snapshot is not None
    assert bad_snapshot is not None
    assert bad_snapshot.smoothed_score > good_snapshot.smoothed_score
    assert bad_snapshot.tier1.tool_error_rate > good_snapshot.tier1.tool_error_rate


def test_score_snapshots_apply_smoothing_over_recent_raw_scores() -> None:
    episodes = segment_messages(load_messages(BAD_FIXTURE_PATH))["main"]

    snapshots = build_score_snapshots(
        episodes,
        config=Config(),
        window_size=5,
        smoothing_window=3,
    )

    assert len(snapshots) == 3
    expected_smoothed = round(
        sum(snapshot.raw_score for snapshot in snapshots[-3:]) / 3,
        2,
    )
    assert round(snapshots[-1].smoothed_score, 2) == expected_smoothed


def test_score_store_persists_and_reads_latest_snapshot(tmp_path: Path) -> None:
    store = ScoreStore(tmp_path / "scores.sqlite3")
    store.initialize()

    episodes = segment_messages(load_messages(GOOD_FIXTURE_PATH))["main"]
    snapshots = build_score_snapshots(episodes, config=CONFIG)
    for snapshot in snapshots:
        store.persist_snapshot(
            transcript_path=GOOD_FIXTURE_PATH,
            chain_id="main",
            snapshot=snapshot,
        )

    latest = store.fetch_latest_snapshot(transcript_path=GOOD_FIXTURE_PATH)

    assert latest is not None
    assert latest["episode_count"] == len(snapshots)
    assert latest["smoothed_score"] == snapshots[-1].smoothed_score


def test_run_command_prints_detailed_score_and_metrics(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "run",
            str(GOOD_FIXTURE_PATH),
            "--store-path",
            str(tmp_path / "run.sqlite3"),
        ],
    )

    assert result.exit_code == 0
    assert "Drift score:" in result.stdout
    assert "Diagnosis:" in result.stdout
    assert "Signals:" in result.stdout
    assert "Assistant activity:" in result.stdout
    assert "Technical detail:" in result.stdout
