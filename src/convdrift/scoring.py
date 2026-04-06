from __future__ import annotations

from dataclasses import dataclass

from .metrics import Tier1Metrics, compute_tier1_metrics
from .models import Episode


DEFAULT_WINDOW_SIZE = 5
DEFAULT_SMOOTHING_WINDOW = 3
TIER1_WEIGHTS = {
    "tool_error_rate": 0.45,
    "action_mix_score": 0.35,
    "user_message_length_trend_score": 0.20,
}


@dataclass(slots=True)
class ScoreSnapshot:
    episode_count: int
    window_size: int
    raw_score: float
    smoothed_score: float
    metrics: Tier1Metrics


def build_score_snapshots(
    episodes: list[Episode],
    *,
    window_size: int = DEFAULT_WINDOW_SIZE,
    smoothing_window: int = DEFAULT_SMOOTHING_WINDOW,
) -> list[ScoreSnapshot]:
    snapshots: list[ScoreSnapshot] = []
    raw_scores: list[float] = []

    for index in range(len(episodes)):
        window_start = max(0, index + 1 - window_size)
        window = episodes[window_start : index + 1]
        metrics = compute_tier1_metrics(window)
        raw_score = _compute_raw_tier1_score(metrics)
        raw_scores.append(raw_score)
        smoothing_slice = raw_scores[-smoothing_window:]
        smoothed_score = sum(smoothing_slice) / len(smoothing_slice)
        snapshots.append(
            ScoreSnapshot(
                episode_count=index + 1,
                window_size=len(window),
                raw_score=raw_score,
                smoothed_score=smoothed_score,
                metrics=metrics,
            )
        )

    return snapshots


def latest_score_snapshot(
    episodes: list[Episode],
    *,
    window_size: int = DEFAULT_WINDOW_SIZE,
    smoothing_window: int = DEFAULT_SMOOTHING_WINDOW,
) -> ScoreSnapshot | None:
    snapshots = build_score_snapshots(
        episodes,
        window_size=window_size,
        smoothing_window=smoothing_window,
    )
    if not snapshots:
        return None
    return snapshots[-1]


def _compute_raw_tier1_score(metrics: Tier1Metrics) -> float:
    # `action_mix_score` already encodes non-productive pressure, so it can be
    # combined directly with the other drift-oriented signals here.
    normalized_score = (
        metrics.tool_error_rate * TIER1_WEIGHTS["tool_error_rate"]
        + metrics.action_mix_score * TIER1_WEIGHTS["action_mix_score"]
        + metrics.user_message_length_trend_score
        * TIER1_WEIGHTS["user_message_length_trend_score"]
    )
    return round(normalized_score * 100, 2)
