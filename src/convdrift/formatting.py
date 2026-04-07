from __future__ import annotations

from .config import Config
from .scoring import ScoreSnapshot


def format_snapshot(
    *,
    snapshot: ScoreSnapshot,
    config: Config,
    transcript_path: str,
    store_path: str,
    sidechain_count: int,
    output_format: str,
) -> str:
    if output_format == "score-only":
        return f"D:{round(snapshot.smoothed_score):.0f}"
    if output_format == "with-metrics":
        return (
            f"D:{round(snapshot.smoothed_score):.0f} "
            f"[err:{snapshot.tier1.tool_error_rate:.2f} "
            f"rep:{snapshot.tier2.lexical_stagnation_index:.2f} "
            f"cor:{snapshot.tier2.correction_density:.2f}]"
        )
    if output_format == "by-tier":
        return (
            f"D:{round(snapshot.smoothed_score):.0f} "
            f"T1:{round(snapshot.tier1_score):.0f} "
            f"T2:{round(snapshot.tier2_score):.0f}"
        )
    return _format_full(
        snapshot=snapshot,
        config=config,
        transcript_path=transcript_path,
        store_path=store_path,
        sidechain_count=sidechain_count,
    )


def _format_full(
    *,
    snapshot: ScoreSnapshot,
    config: Config,
    transcript_path: str,
    store_path: str,
    sidechain_count: int,
) -> str:
    action_mix = snapshot.tier1.action_mix
    lines = [
        f"Transcript: {transcript_path}",
        f"Drift score: {snapshot.smoothed_score:.2f} "
        f"({describe_score_band(snapshot.smoothed_score, config)}) "
        f"(raw={snapshot.raw_score:.2f}, episodes={snapshot.episode_count}, "
        f"window={snapshot.window_size})",
        f"Store: {store_path}",
        f"Tier scores: T1={snapshot.tier1_score:.2f} T2={snapshot.tier2_score:.2f}",
        "Metrics: "
        f"err={snapshot.tier1.tool_error_rate:.2f} "
        f"mix={snapshot.tier1.action_mix_score:.2f} "
        f"user_trend={snapshot.tier1.user_message_length_trend_score:.2f} "
        f"rep={snapshot.tier2.lexical_stagnation_index:.2f} "
        f"cor={snapshot.tier2.correction_density:.2f} "
        f"token_asym={_format_optional(snapshot.tier1.token_asymmetry_ratio)} "
        f"cache_drop={_format_optional(snapshot.tier1.cache_efficiency_drop)}",
        "Action mix: "
        f"productive={action_mix.productive:.2f} "
        f"exploratory={action_mix.exploratory:.2f} "
        f"recursive={action_mix.recursive:.2f}",
    ]
    if sidechain_count:
        lines.append(
            f"Sidechains detected: {sidechain_count} (not included in main score)"
        )
    return "\n".join(lines)


def describe_score_band(score: float, config: Config) -> str:
    if score <= config.thresholds.healthy_max:
        return "healthy"
    if score <= config.thresholds.mild_max:
        return "mild drift"
    if score <= config.thresholds.significant_max:
        return "significant drift"
    return "critical drift"


def _format_optional(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.2f}"
