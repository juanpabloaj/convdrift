from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from datetime import UTC, datetime
from hashlib import sha1
from pathlib import Path

from .scoring import ScoreSnapshot


class ScoreStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def initialize(self) -> None:
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    transcript_path TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS scores (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    chain_id TEXT NOT NULL,
                    episode_count INTEGER NOT NULL,
                    window_size INTEGER NOT NULL,
                    raw_score REAL NOT NULL,
                    smoothed_score REAL NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(session_id, chain_id, episode_count),
                    FOREIGN KEY(session_id) REFERENCES sessions(id)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    score_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    value REAL,
                    details TEXT,
                    UNIQUE(score_id, name),
                    FOREIGN KEY(score_id) REFERENCES scores(id)
                )
                """
            )

    def persist_snapshot(
        self,
        *,
        transcript_path: str | Path,
        chain_id: str,
        snapshot: ScoreSnapshot,
    ) -> None:
        session_id = build_session_id(transcript_path)
        timestamp = _utc_now()

        with sqlite3.connect(self.path) as connection:
            connection.execute(
                """
                INSERT INTO sessions (id, transcript_path, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(transcript_path) DO UPDATE SET
                    updated_at = excluded.updated_at
                """,
                (session_id, str(Path(transcript_path)), timestamp, timestamp),
            )
            connection.execute(
                """
                INSERT INTO scores (
                    session_id,
                    chain_id,
                    episode_count,
                    window_size,
                    raw_score,
                    smoothed_score,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id, chain_id, episode_count) DO UPDATE SET
                    window_size = excluded.window_size,
                    raw_score = excluded.raw_score,
                    smoothed_score = excluded.smoothed_score,
                    created_at = excluded.created_at
                """,
                (
                    session_id,
                    chain_id,
                    snapshot.episode_count,
                    snapshot.window_size,
                    snapshot.raw_score,
                    snapshot.smoothed_score,
                    timestamp,
                ),
            )
            score_id = connection.execute(
                """
                SELECT id
                FROM scores
                WHERE session_id = ? AND chain_id = ? AND episode_count = ?
                """,
                (session_id, chain_id, snapshot.episode_count),
            ).fetchone()[0]

            metric_rows = [
                ("tool_error_rate", snapshot.metrics.tool_error_rate, None),
                (
                    "action_mix_score",
                    snapshot.metrics.action_mix_score,
                    json.dumps(asdict(snapshot.metrics.action_mix)),
                ),
                (
                    "user_message_length_slope",
                    snapshot.metrics.user_message_length_slope,
                    None,
                ),
                (
                    "user_message_length_trend_score",
                    snapshot.metrics.user_message_length_trend_score,
                    None,
                ),
                (
                    "token_asymmetry_ratio",
                    snapshot.metrics.token_asymmetry_ratio,
                    None,
                ),
                (
                    "cache_efficiency_drop",
                    snapshot.metrics.cache_efficiency_drop,
                    None,
                ),
            ]

            for name, value, details in metric_rows:
                connection.execute(
                    """
                    INSERT INTO metrics (score_id, name, value, details)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(score_id, name) DO UPDATE SET
                        value = excluded.value,
                        details = excluded.details
                    """,
                    (score_id, name, value, details),
                )

    def fetch_latest_snapshot(
        self,
        *,
        transcript_path: str | Path,
        chain_id: str = "main",
    ) -> dict[str, object] | None:
        session_id = build_session_id(transcript_path)
        with sqlite3.connect(self.path) as connection:
            score_row = connection.execute(
                """
                SELECT id, episode_count, window_size, raw_score, smoothed_score, created_at
                FROM scores
                WHERE session_id = ? AND chain_id = ?
                ORDER BY episode_count DESC
                LIMIT 1
                """,
                (session_id, chain_id),
            ).fetchone()
            if score_row is None:
                return None

            metric_rows = connection.execute(
                """
                SELECT name, value, details
                FROM metrics
                WHERE score_id = ?
                ORDER BY name
                """,
                (score_row[0],),
            ).fetchall()

        return {
            "episode_count": score_row[1],
            "window_size": score_row[2],
            "raw_score": score_row[3],
            "smoothed_score": score_row[4],
            "created_at": score_row[5],
            "metrics": [
                {"name": name, "value": value, "details": details}
                for name, value, details in metric_rows
            ],
        }


def build_session_id(transcript_path: str | Path) -> str:
    resolved = str(Path(transcript_path).resolve())
    return sha1(resolved.encode("utf-8")).hexdigest()


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()
