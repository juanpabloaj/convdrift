from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import typer
from watchfiles import watch

from ._utils import transcript_was_updated
from .config import DEFAULT_CONFIG_PATH, default_config_text, load_config
from .formatting import format_snapshot
from .history import (
    DEFAULT_SESSIONS_DIR,
    append_session_timeline,
    list_session_summaries,
    read_session_timeline,
)
from .parser import load_messages
from .scoring import build_score_snapshots
from .segmenter import segment_messages
from .statusline import StoredSnapshot, format_statusline
from .store import DEFAULT_STORE_PATH, ScoreStore

app = typer.Typer(
    help="Session stagnation and looping detection for Claude Code transcripts.",
    no_args_is_help=True,
)
config_app = typer.Typer(help="Configuration helpers.")
app.add_typer(config_app, name="config")


@dataclass(slots=True)
class AnalysisResult:
    snapshots: list
    episodes_by_chain: dict[str, list]


@app.callback()
def main() -> None:
    """convdrift CLI."""


@app.command()
def segment(transcript: Path) -> None:
    """Print a summary of segmented episodes for a transcript."""
    messages = load_messages(transcript)
    episodes_by_chain = segment_messages(messages)

    typer.echo(f"Transcript: {transcript}")
    typer.echo(f"Messages: {len(messages)}")

    for chain_id, episodes in sorted(episodes_by_chain.items()):
        typer.echo(f"{chain_id}: {len(episodes)} episode(s)")
        for episode in episodes:
            counts = ", ".join(
                f"{role}={count}"
                for role, count in sorted(episode.message_type_counts.items())
            )
            typer.echo(
                f"  - episode {episode.sequence}: "
                f"{episode.message_count} message(s) [{counts}]"
            )


@app.command()
def run(
    transcript: Path,
    *,
    store_path: Path | None = typer.Option(None),
    follow: bool = typer.Option(False, "--follow/--no-follow"),
    config_path: Path | None = typer.Option(None),
    output_format: str | None = typer.Option(None),
    sessions_dir: Path = typer.Option(DEFAULT_SESSIONS_DIR),
) -> None:
    """Compute and persist the current composite drift score for the main chain."""
    config = load_config(config_path)
    resolved_output_format = output_format or config.analysis.output_format
    resolved_store_path = store_path or DEFAULT_STORE_PATH
    score_store = ScoreStore(resolved_store_path)
    score_store.initialize()

    run_analysis_loop(
        transcript=transcript,
        score_store=score_store,
        config=config,
        output_format=resolved_output_format,
        follow=follow,
        sessions_dir=sessions_dir,
        emitter=typer.echo,
    )


@app.command("statusline-run")
def statusline_run(
    *,
    store_path: Path | None = typer.Option(None),
    config_path: Path | None = typer.Option(None),
    output_format: str | None = typer.Option(None),
    sessions_dir: Path = typer.Option(DEFAULT_SESSIONS_DIR),
) -> None:
    """Claude Code statusline entrypoint: read stdin JSON, analyze once, print indicator."""
    status_context = _read_status_context()
    transcript_value = status_context.get("transcript_path") or status_context.get(
        "transcriptPath"
    )
    transcript_path = Path(str(transcript_value).strip()) if transcript_value else None
    if transcript_path is None or not str(transcript_path).strip():
        return

    config = load_config(config_path)
    resolved_output_format = _resolve_statusline_output_format(
        config_path=config_path,
        config=config,
        output_format=output_format,
    )
    resolved_store_path = store_path or DEFAULT_STORE_PATH
    score_store = ScoreStore(resolved_store_path)
    score_store.initialize()

    analysis_result = _analyze_transcript(
        transcript=transcript_path,
        score_store=score_store,
        config=config,
        sessions_dir=sessions_dir,
    )
    if analysis_result is None or not resolved_store_path.exists():
        return

    snapshot = score_store.fetch_latest_snapshot(transcript_path=transcript_path)
    if snapshot is None:
        return

    typer.echo(_render_statusline_from_snapshot(snapshot, resolved_output_format))


def _analyze_transcript(
    *,
    transcript: Path,
    score_store: ScoreStore,
    config,
    sessions_dir: Path,
) -> AnalysisResult | None:
    episodes_by_chain = segment_messages(load_messages(transcript))
    main_episodes = episodes_by_chain.get("main", [])
    snapshots = build_score_snapshots(main_episodes, config=config)
    if not snapshots:
        typer.echo("No mainline episodes found.")
        return None

    for snapshot in snapshots:
        score_store.persist_snapshot(
            transcript_path=transcript,
            chain_id="main",
            snapshot=snapshot,
        )
        append_session_timeline(
            transcript_path=transcript,
            snapshot=snapshot,
            sessions_dir=sessions_dir,
        )

    return AnalysisResult(
        snapshots=snapshots,
        episodes_by_chain=episodes_by_chain,
    )


def run_analysis_loop(
    *,
    transcript: Path,
    score_store: ScoreStore,
    config,
    output_format: str,
    follow: bool,
    sessions_dir: Path,
    emitter: Callable[[str], None],
    max_updates: int | None = None,
) -> None:
    last_printed_episode_count = 0
    updates = 0

    while True:
        analysis_result = _analyze_transcript(
            transcript=transcript,
            score_store=score_store,
            config=config,
            sessions_dir=sessions_dir,
        )
        if analysis_result is not None:
            latest = analysis_result.snapshots[-1]
            latest_episode_count = latest.episode_count
        else:
            latest_episode_count = None

        if (
            latest_episode_count is not None
            and latest_episode_count != last_printed_episode_count
        ):
            _emit_score_snapshot(
                transcript=transcript,
                score_store=score_store,
                snapshot=latest,
                sidechain_count=max(0, len(analysis_result.episodes_by_chain) - 1),
                config=config,
                output_format=output_format,
                emitter=emitter,
            )
            last_printed_episode_count = latest_episode_count
            updates += 1

        if not follow:
            break
        if max_updates is not None and updates >= max_updates:
            break

        for changes in watch(transcript.parent, recursive=False):
            if transcript_was_updated(changes, transcript):
                break


def _emit_score_snapshot(
    *,
    transcript: Path,
    score_store: ScoreStore,
    snapshot,
    sidechain_count: int,
    config,
    output_format: str,
    emitter: Callable[[str], None],
) -> None:
    emitter(
        format_snapshot(
            snapshot=snapshot,
            config=config,
            transcript_path=str(transcript),
            store_path=str(score_store.path),
            sidechain_count=sidechain_count,
            output_format=output_format,
        )
    )


def _render_statusline_from_snapshot(
    snapshot: dict[str, object],
    output_format: str,
) -> str:
    metrics = {metric["name"]: metric["value"] for metric in snapshot["metrics"]}
    return format_statusline(
        StoredSnapshot(
            smoothed_score=float(snapshot["smoothed_score"]),
            tier1_score=float(snapshot["tier1_score"] or 0.0),
            tier2_score=float(snapshot["tier2_score"] or 0.0),
            tool_error_rate=_optional_float(metrics.get("tool_error_rate")),
            lexical_stagnation_index=_optional_float(
                metrics.get("lexical_stagnation_index")
            ),
            correction_marker_rate=_optional_float(
                metrics.get("correction_marker_rate")
            ),
        ),
        output_format=output_format,
    )


def _resolve_statusline_output_format(
    *,
    config_path: Path | None,
    config,
    output_format: str | None,
) -> str:
    if output_format is not None:
        return _normalize_statusline_output_format(output_format)
    if config_path is not None or DEFAULT_CONFIG_PATH.exists():
        return _normalize_statusline_output_format(config.analysis.output_format)
    return "with-metrics"


def _read_status_context() -> dict[str, object]:
    try:
        raw = typer.get_text_stream("stdin").read()
        if not raw.strip():
            return {}
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    return data


@config_app.command("init")
def config_init(path: Path = typer.Option(DEFAULT_CONFIG_PATH)) -> None:
    """Write a default convdrift.toml configuration file."""
    if path.exists():
        raise typer.BadParameter(f"Refusing to overwrite existing config: {path}")
    path.write_text(default_config_text(), encoding="utf-8")
    typer.echo(f"Wrote default config to {path}")


@app.command()
def log(
    session_id: str,
    *,
    sessions_dir: Path = typer.Option(DEFAULT_SESSIONS_DIR),
) -> None:
    """Print the stored drift timeline for a past session."""
    entries = read_session_timeline(session_id, sessions_dir=sessions_dir)
    if not entries:
        raise typer.BadParameter(f"No timeline found for session: {session_id}")

    for entry in entries:
        typer.echo(
            f"episode={entry['episode_count']} "
            f"score={entry['smoothed_score']:.2f} "
            f"t1={entry['tier1_score']:.2f} "
            f"t2={entry['tier2_score']:.2f}"
        )


@app.command()
def sessions(
    *,
    sessions_dir: Path = typer.Option(DEFAULT_SESSIONS_DIR),
) -> None:
    """List recorded session timelines."""
    summaries = list_session_summaries(sessions_dir=sessions_dir)
    if not summaries:
        typer.echo("No recorded sessions found.")
        return

    for summary in summaries:
        typer.echo(
            f"{summary['session_id']} "
            f"episodes={summary['episode_count']} "
            f"score={summary['smoothed_score']:.2f} "
            f"path={summary['transcript_path']}"
        )


@app.command()
def statusline(
    store_path: Path,
    *,
    transcript: Path | None = typer.Option(None),
    session_id: str | None = typer.Option(None),
    chain_id: str = typer.Option("main"),
    output_format: str = typer.Option("with-metrics"),
) -> None:
    """Read the score store and render a compact statusline indicator."""
    score_store = ScoreStore(store_path)
    snapshot = None
    if transcript is not None:
        snapshot = score_store.fetch_latest_snapshot(
            transcript_path=transcript,
            chain_id=chain_id,
        )
    elif session_id is not None:
        snapshot = score_store.fetch_latest_snapshot_for_session(
            session_id=session_id,
            chain_id=chain_id,
        )
    else:
        raise typer.BadParameter("Provide either --transcript or --session-id.")

    if snapshot is None:
        raise typer.BadParameter("No snapshot found for the requested session.")

    typer.echo(
        _render_statusline_from_snapshot(
            snapshot,
            _normalize_statusline_output_format(output_format),
        )
    )


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    return float(value)


def _normalize_statusline_output_format(output_format: str) -> str:
    if output_format in {"score-only", "with-metrics"}:
        return output_format
    raise typer.BadParameter(
        f"Format '{output_format}' is not supported for statusline. "
        "Use 'score-only' or 'with-metrics'."
    )
