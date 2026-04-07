from pathlib import Path

from typer.testing import CliRunner

from convdrift.cli import app
from convdrift.config import Config, default_config_text, load_config
from convdrift.metrics import (
    _classify_tool_call,
    _classify_bash_call,
    _extract_ngrams,
    compute_tier2_metrics,
)
from convdrift.models import ToolCall
from convdrift.parser import load_messages
from convdrift.scoring import latest_score_snapshot
from convdrift.segmenter import segment_messages


FIXTURES_DIR = Path(__file__).parent / "fixtures"
GOOD_FIXTURE_PATH = FIXTURES_DIR / "stage1_good_transcript.jsonl"
BAD_FIXTURE_PATH = FIXTURES_DIR / "stage1_bad_transcript.jsonl"
REPETITIVE_FIXTURE_PATH = FIXTURES_DIR / "stage2_repetitive_transcript.jsonl"


def test_extract_ngrams_preserves_unicode_tokens() -> None:
    ngrams = _extract_ngrams("revisión del código añadido", ngram_size=2)
    tokens = {token for pair in ngrams for token in pair}
    assert "revisión" in tokens
    assert "código" in tokens
    assert "añadido" in tokens


def test_bash_build_and_test_commands_classified_as_neutral() -> None:
    neutral_commands = [
        "pytest tests/",
        "uv run pytest",
        "npm test",
        "npm run build",
        "make test",
        "cargo test",
        "go test ./...",
    ]
    for command in neutral_commands:
        tool_call = ToolCall(name="bash", input={"command": command})
        result = _classify_bash_call(tool_call)
        assert result == "neutral", (
            f"Expected 'neutral' for '{command}', got '{result}'"
        )


def test_unknown_tool_defaults_to_neutral() -> None:
    tool_call = ToolCall(name="mcp__some_tool", input={"query": "status"})

    assert _classify_tool_call(tool_call) == "neutral"


def test_tier2_metrics_detect_repetition_and_corrections() -> None:
    config = Config()
    episodes = segment_messages(load_messages(REPETITIVE_FIXTURE_PATH))["main"]

    metrics = compute_tier2_metrics(episodes, config=config)

    assert metrics.lexical_stagnation_index > 0.8
    assert metrics.correction_marker_rate > 0.5


def test_weight_overrides_change_composite_score(tmp_path: Path) -> None:
    config_path = tmp_path / "convdrift.toml"
    config_path.write_text(default_config_text(), encoding="utf-8")
    config_path.write_text(
        config_path.read_text(encoding="utf-8").replace(
            "tier1 = 0.5\ntier2 = 0.3\ntier3 = 0.2",
            "tier1 = 0.1\ntier2 = 0.9\ntier3 = 0.0",
        ),
        encoding="utf-8",
    )
    custom_config = load_config(config_path)
    default_config = Config()
    episodes = segment_messages(load_messages(REPETITIVE_FIXTURE_PATH))["main"]

    default_snapshot = latest_score_snapshot(episodes, config=default_config)
    custom_snapshot = latest_score_snapshot(episodes, config=custom_config)

    assert default_snapshot is not None
    assert custom_snapshot is not None
    assert custom_snapshot.smoothed_score != default_snapshot.smoothed_score


def test_config_init_writes_default_file(tmp_path: Path) -> None:
    runner = CliRunner()
    config_path = tmp_path / "convdrift.toml"

    result = runner.invoke(app, ["config", "init", "--path", str(config_path)])

    assert result.exit_code == 0
    assert config_path.exists()
    assert "[analysis]" in config_path.read_text(encoding="utf-8")


def test_run_supports_stage2_output_formats(tmp_path: Path) -> None:
    runner = CliRunner()
    store_path = tmp_path / "run.sqlite3"

    result = runner.invoke(
        app,
        [
            "run",
            str(BAD_FIXTURE_PATH),
            "--store-path",
            str(store_path),
            "--output-format",
            "by-tier",
        ],
    )

    assert result.exit_code == 0
    assert "D:" in result.stdout
    assert "T1:" in result.stdout
    assert "T2:" in result.stdout
