from __future__ import annotations

from pathlib import Path

import typer
from watchfiles import watch

from ._utils import transcript_was_updated
from .config import DEFAULT_CONFIG_PATH, default_config_text, load_config
from .formatting import format_snapshot
from .parser import load_messages
from .scoring import build_score_snapshots
from .segmenter import segment_messages
from .store import ScoreStore

app = typer.Typer(
    help="Session stagnation and looping detection for Claude Code transcripts.",
    no_args_is_help=True,
)
config_app = typer.Typer(help="Configuration helpers.")
app.add_typer(config_app, name="config")


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
) -> None:
    """Compute and persist the current composite drift score for the main chain."""
    config = load_config(config_path)
    resolved_output_format = output_format or config.analysis.output_format
    resolved_store_path = store_path or transcript.parent / ".convdrift.sqlite3"
    score_store = ScoreStore(resolved_store_path)
    score_store.initialize()

    last_printed_episode_count = 0
    while True:
        latest_episode_count = _analyze_transcript(
            transcript=transcript,
            score_store=score_store,
            config=config,
            output_format=resolved_output_format,
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
    config,
    output_format: str,
    last_printed_episode_count: int,
) -> int | None:
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

    latest = snapshots[-1]
    if latest.episode_count != last_printed_episode_count:
        _print_score_snapshot(
            transcript=transcript,
            score_store=score_store,
            snapshot=latest,
            sidechain_count=max(0, len(episodes_by_chain) - 1),
            config=config,
            output_format=output_format,
        )
    return latest.episode_count


def _print_score_snapshot(
    *,
    transcript: Path,
    score_store: ScoreStore,
    snapshot,
    sidechain_count: int,
    config,
    output_format: str,
) -> None:
    typer.echo(
        format_snapshot(
            snapshot=snapshot,
            config=config,
            transcript_path=str(transcript),
            store_path=str(score_store.path),
            sidechain_count=sidechain_count,
            output_format=output_format,
        )
    )


@config_app.command("init")
def config_init(path: Path = typer.Option(DEFAULT_CONFIG_PATH)) -> None:
    """Write a default convdrift.toml configuration file."""
    if path.exists():
        raise typer.BadParameter(f"Refusing to overwrite existing config: {path}")
    path.write_text(default_config_text(), encoding="utf-8")
    typer.echo(f"Wrote default config to {path}")
