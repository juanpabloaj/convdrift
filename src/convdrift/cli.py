from __future__ import annotations

from pathlib import Path

import typer

from .parser import load_messages
from .segmenter import segment_messages

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
