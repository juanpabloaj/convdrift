from __future__ import annotations

from pathlib import Path

import typer
from watchfiles import watch

from ._utils import transcript_was_updated
from .parser import load_messages
from .scoring import (
    DEFAULT_SMOOTHING_WINDOW,
    DEFAULT_WINDOW_SIZE,
    build_score_snapshots,
)
from .segmenter import segment_messages
from .store import ScoreStore

app = typer.Typer(
    help="Session stagnation and looping detection for Claude Code transcripts.",
    no_args_is_help=True,
)


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
    window_size: int = typer.Option(DEFAULT_WINDOW_SIZE, min=1),
    smoothing_window: int = typer.Option(DEFAULT_SMOOTHING_WINDOW, min=1),
    store_path: Path | None = typer.Option(None),
    follow: bool = typer.Option(False, "--follow/--no-follow"),
) -> None:
    """Compute and persist a Stage 1 Tier 1 score for the main conversation chain."""
    resolved_store_path = store_path or transcript.parent / ".convdrift.sqlite3"
    score_store = ScoreStore(resolved_store_path)
    score_store.initialize()

    last_printed_episode_count = 0
    while True:
        latest_episode_count = _analyze_transcript(
            transcript=transcript,
            score_store=score_store,
            window_size=window_size,
            smoothing_window=smoothing_window,
            last_printed_episode_count=last_printed_episode_count,
        )
        if latest_episode_count is not None:
            last_printed_episode_count = latest_episode_count

        if not follow:
            break

        for changes in watch(transcript.parent, recursive=False):
            if transcript_was_updated(changes, transcript):
                break


def _analyze_transcript(
    *,
    transcript: Path,
    score_store: ScoreStore,
    window_size: int,
    smoothing_window: int,
    last_printed_episode_count: int,
) -> int | None:
    episodes_by_chain = segment_messages(load_messages(transcript))
    main_episodes = episodes_by_chain.get("main", [])
    snapshots = build_score_snapshots(
        main_episodes,
        window_size=window_size,
        smoothing_window=smoothing_window,
    )
    if not snapshots:
        typer.echo("No mainline episodes found.")
        return None

    for snapshot in snapshots:
        score_store.persist_snapshot(
            transcript_path=transcript,
            chain_id="main",
            snapshot=snapshot,
        )

    latest = snapshots[-1]
    if latest.episode_count != last_printed_episode_count:
        _print_score_snapshot(
            transcript=transcript,
            score_store=score_store,
            snapshot=latest,
            sidechain_count=max(0, len(episodes_by_chain) - 1),
        )
    return latest.episode_count


def _print_score_snapshot(
    *,
    transcript: Path,
    score_store: ScoreStore,
    snapshot,
    sidechain_count: int,
) -> None:
    action_mix = snapshot.metrics.action_mix
    typer.echo(f"Transcript: {transcript}")
    typer.echo(
        f"Tier 1 score: {snapshot.smoothed_score:.2f} "
        f"(raw={snapshot.raw_score:.2f}, episodes={snapshot.episode_count}, "
        f"window={snapshot.window_size})"
    )
    typer.echo(f"Store: {score_store.path}")
    typer.echo(
        "Metrics: "
        f"err={snapshot.metrics.tool_error_rate:.2f} "
        f"mix={snapshot.metrics.action_mix_score:.2f} "
        f"user_trend={snapshot.metrics.user_message_length_trend_score:.2f} "
        f"token_asym={_format_optional(snapshot.metrics.token_asymmetry_ratio)} "
        f"cache_drop={_format_optional(snapshot.metrics.cache_efficiency_drop)}"
    )
    typer.echo(
        "Action mix: "
        f"productive={action_mix.productive:.2f} "
        f"exploratory={action_mix.exploratory:.2f} "
        f"recursive={action_mix.recursive:.2f}"
    )
    if sidechain_count:
        typer.echo(
            f"Sidechains detected: {sidechain_count} (not included in main score)"
        )


def _format_optional(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.2f}"
