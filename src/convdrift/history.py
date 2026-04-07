from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .scoring import ScoreSnapshot
from .store import build_session_id


DEFAULT_SESSIONS_DIR = Path.home() / ".convdrift" / "sessions"


def append_session_timeline(
    *,
    transcript_path: str | Path,
    snapshot: ScoreSnapshot,
    sessions_dir: str | Path = DEFAULT_SESSIONS_DIR,
    chain_id: str = "main",
) -> None:
    session_id = build_session_id(transcript_path)
    path = session_log_path(session_id=session_id, sessions_dir=sessions_dir)
    path.parent.mkdir(parents=True, exist_ok=True)

    latest_entry = read_latest_session_entry(
        session_id=session_id, sessions_dir=sessions_dir
    )
    if (
        latest_entry is not None
        and int(latest_entry["episode_count"]) >= snapshot.episode_count
    ):
        return

    entry = {
        "session_id": session_id,
        "transcript_path": str(Path(transcript_path)),
        "chain_id": chain_id,
        "episode_count": snapshot.episode_count,
        "window_size": snapshot.window_size,
        "raw_score": snapshot.raw_score,
        "smoothed_score": snapshot.smoothed_score,
        "tier1_score": snapshot.tier1_score,
        "tier2_score": snapshot.tier2_score,
        "active_tiers": list(snapshot.active_tiers),
        "metrics": {
            "tool_error_rate": snapshot.tier1.tool_error_rate,
            "action_mix_score": snapshot.tier1.action_mix_score,
            "user_message_length_trend_score": snapshot.tier1.user_message_length_trend_score,
            "lexical_stagnation_index": snapshot.tier2.lexical_stagnation_index,
            "correction_density": snapshot.tier2.correction_density,
        },
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry) + "\n")


def list_session_summaries(
    sessions_dir: str | Path = DEFAULT_SESSIONS_DIR,
) -> list[dict[str, Any]]:
    directory = Path(sessions_dir)
    if not directory.exists():
        return []

    summaries: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.jsonl")):
        entries = read_session_timeline(path.stem, sessions_dir=directory)
        if not entries:
            continue
        latest = entries[-1]
        summaries.append(
            {
                "session_id": path.stem,
                "transcript_path": latest["transcript_path"],
                "episode_count": latest["episode_count"],
                "smoothed_score": latest["smoothed_score"],
                "chain_id": latest["chain_id"],
            }
        )
    return summaries


def read_session_timeline(
    session_id: str,
    *,
    sessions_dir: str | Path = DEFAULT_SESSIONS_DIR,
) -> list[dict[str, Any]]:
    path = session_log_path(session_id=session_id, sessions_dir=sessions_dir)
    if not path.exists():
        return []

    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def read_latest_session_entry(
    *,
    session_id: str,
    sessions_dir: str | Path = DEFAULT_SESSIONS_DIR,
) -> dict[str, Any] | None:
    entries = read_session_timeline(session_id, sessions_dir=sessions_dir)
    if not entries:
        return None
    return entries[-1]


def session_log_path(*, session_id: str, sessions_dir: str | Path) -> Path:
    return Path(sessions_dir) / f"{session_id}.jsonl"
