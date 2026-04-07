from __future__ import annotations

from dataclasses import dataclass

from .config import Config
from .metrics import (
    Tier1Metrics,
    Tier2Metrics,
    compute_tier1_metrics,
    compute_tier2_metrics,
)
from .models import Episode


DEFAULT_WINDOW_SIZE = 5
DEFAULT_SMOOTHING_WINDOW = 3


@dataclass(slots=True)
class ScoreSnapshot:
    episode_count: int
    window_size: int
    raw_score: float
    smoothed_score: float
    tier1_score: float
    tier2_score: float
    active_tiers: tuple[str, ...]
    tier1: Tier1Metrics
    tier2: Tier2Metrics


def build_score_snapshots(
    episodes: list[Episode],
    *,
    config: Config | None = None,
    window_size: int | None = None,
    smoothing_window: int | None = None,
) -> list[ScoreSnapshot]:
    config = _resolve_config(
        config=config,
        window_size=window_size,
        smoothing_window=smoothing_window,
    )
    snapshots: list[ScoreSnapshot] = []
    raw_scores: list[float] = []

    for index in range(len(episodes)):
        window_start = max(0, index + 1 - config.analysis.window_size)
        window = episodes[window_start : index + 1]
        tier1 = compute_tier1_metrics(window, config=config)
        tier2 = compute_tier2_metrics(window, config=config)
        tier1_score = _compute_tier1_score(tier1, config=config)
        tier2_score = _compute_tier2_score(tier2, config=config)
        raw_score, active_tiers = _compute_composite_score(
            tier1_score=tier1_score,
            tier2_score=tier2_score,
            config=config,
        )
        raw_scores.append(raw_score)
        smoothing_slice = raw_scores[-config.analysis.smoothing_window :]
        smoothed_score = sum(smoothing_slice) / len(smoothing_slice)
        snapshots.append(
            ScoreSnapshot(
                episode_count=index + 1,
                window_size=len(window),
                raw_score=round(raw_score, 2),
                smoothed_score=round(smoothed_score, 2),
                tier1_score=round(tier1_score, 2),
                tier2_score=round(tier2_score, 2),
                active_tiers=active_tiers,
                tier1=tier1,
                tier2=tier2,
            )
        )

    return snapshots


def latest_score_snapshot(
    episodes: list[Episode],
    *,
    config: Config | None = None,
    window_size: int | None = None,
    smoothing_window: int | None = None,
) -> ScoreSnapshot | None:
    snapshots = build_score_snapshots(
        episodes,
        config=config,
        window_size=window_size,
        smoothing_window=smoothing_window,
    )
    if not snapshots:
        return None
    return snapshots[-1]


def _compute_tier1_score(metrics: Tier1Metrics, *, config: Config) -> float:
    normalized_score = (
        metrics.tool_error_rate * config.tier1_weights.tool_error_rate
        + metrics.action_mix_score * config.tier1_weights.action_mix_score
        + metrics.user_message_length_trend_score
        * config.tier1_weights.user_message_length_trend_score
    )
    return normalized_score * 100


def _compute_tier2_score(metrics: Tier2Metrics, *, config: Config) -> float:
    normalized_score = (
        metrics.lexical_stagnation_index * config.tier2_weights.lexical_stagnation_index
        + metrics.correction_density * config.tier2_weights.correction_density
    )
    return normalized_score * 100


def _compute_composite_score(
    *,
    tier1_score: float,
    tier2_score: float,
    config: Config,
) -> tuple[float, tuple[str, ...]]:
    weighted_scores = [
        ("tier1", tier1_score, config.tier_weights.tier1),
        ("tier2", tier2_score, config.tier_weights.tier2),
    ]
    active = [
        (name, score, weight) for name, score, weight in weighted_scores if weight > 0
    ]
    total_weight = sum(weight for _, _, weight in active)
    if total_weight == 0:
        return 0.0, tuple()

    composite = sum(score * weight for _, score, weight in active) / total_weight
    return composite, tuple(name for name, _, _ in active)


def _resolve_config(
    *,
    config: Config | None,
    window_size: int | None,
    smoothing_window: int | None,
) -> Config:
    resolved = config or Config()
    if window_size is not None:
        resolved.analysis.window_size = window_size
    if smoothing_window is not None:
        resolved.analysis.smoothing_window = smoothing_window
    return resolved
