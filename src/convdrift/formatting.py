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
            f"cor:{snapshot.tier2.correction_marker_rate:.2f}]"
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
    diagnosis = _describe_diagnosis(snapshot)
    lines = [
        f"Transcript: {transcript_path}",
        f"Drift score: {round(snapshot.smoothed_score):.0f} "
        f"({describe_score_band(snapshot.smoothed_score, config)})",
        f"Window: last {snapshot.window_size} episodes ({snapshot.episode_count} total)",
        f"Store: {store_path}",
        f"Diagnosis: {diagnosis}",
        "Signals:",
        f"- Tool errors: {_format_percent(snapshot.tier1.tool_error_rate)}",
        f"- Repetition: {_format_percent(snapshot.tier2.lexical_stagnation_index)}",
        f"- User corrections: {_format_percent(snapshot.tier2.correction_marker_rate)}",
        f"- User re-explaining: {_format_percent(snapshot.tier1.user_message_length_trend_score)}",
        "Assistant activity:",
        f"- Productive: {_format_percent(action_mix.productive)}",
        f"- Exploratory: {_format_percent(action_mix.exploratory)}",
        f"- Recursive: {_format_percent(action_mix.recursive)}",
        f"- Neutral: {_format_percent(action_mix.neutral)}",
        "Technical detail:",
        f"- Raw score: {snapshot.raw_score:.2f}",
        f"- Tier 1: {snapshot.tier1_score:.2f}",
        f"- Tier 2: {snapshot.tier2_score:.2f}",
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


def _format_percent(value: float) -> str:
    return f"{round(value * 100):.0f}%"


def _describe_diagnosis(snapshot: ScoreSnapshot) -> str:
    signals = [
        ("Tool errors", snapshot.tier1.tool_error_rate),
        ("Repetition", snapshot.tier2.lexical_stagnation_index),
        ("User corrections", snapshot.tier2.correction_marker_rate),
        ("User re-explaining", snapshot.tier1.user_message_length_trend_score),
    ]
    strongest_name, strongest_value = max(signals, key=lambda item: item[1])
    if strongest_value <= 0:
        return "No significant drift signals detected."
    return (
        f"Strongest signal in this window: {strongest_name.lower()} "
        f"({_format_percent(strongest_value)})."
    )
