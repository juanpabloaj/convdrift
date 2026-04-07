from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class StoredSnapshot:
    smoothed_score: float
    tier1_score: float
    tier2_score: float
    tool_error_rate: float | None
    lexical_stagnation_index: float | None
    correction_marker_rate: float | None


def format_statusline(snapshot: StoredSnapshot, *, output_format: str) -> str:
    if output_format == "score-only":
        return f"D:{round(snapshot.smoothed_score):.0f}"
    if output_format == "with-metrics":
        return (
            f"D:{round(snapshot.smoothed_score):.0f} "
            f"[err:{_fmt(snapshot.tool_error_rate)} "
            f"rep:{_fmt(snapshot.lexical_stagnation_index)} "
            f"cor:{_fmt(snapshot.correction_marker_rate)}]"
        )
    if output_format == "by-tier":
        return (
            f"D:{round(snapshot.smoothed_score):.0f} "
            f"T1:{round(snapshot.tier1_score):.0f} "
            f"T2:{round(snapshot.tier2_score):.0f}"
        )
    return (
        f"D:{round(snapshot.smoothed_score):.0f} "
        f"T1:{round(snapshot.tier1_score):.0f} "
        f"T2:{round(snapshot.tier2_score):.0f} "
        f"[err:{_fmt(snapshot.tool_error_rate)} "
        f"rep:{_fmt(snapshot.lexical_stagnation_index)} "
        f"cor:{_fmt(snapshot.correction_marker_rate)}]"
    )


def _fmt(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.1f}"
