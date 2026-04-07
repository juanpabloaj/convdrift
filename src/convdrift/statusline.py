from __future__ import annotations

from dataclasses import dataclass

SIGNAL_THRESHOLD = 0.20


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
        label = f"{_describe_score_band(snapshot.smoothed_score)} {round(snapshot.smoothed_score):.0f}"
        signals = _top_signals(snapshot)
        if not signals:
            return label
        return f"{label} | {' | '.join(signals)}"
    raise ValueError(f"Unsupported statusline output format: {output_format}")


def _fmt(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.1f}"


def _describe_score_band(score: float) -> str:
    if score <= 25:
        return "Healthy"
    if score <= 50:
        return "Mild drift"
    if score <= 75:
        return "Significant drift"
    return "Stuck"


def _top_signals(snapshot: StoredSnapshot) -> list[str]:
    candidates = [
        ("errors", snapshot.tool_error_rate),
        ("repetition", snapshot.lexical_stagnation_index),
        ("corrections", snapshot.correction_marker_rate),
    ]
    visible = [
        (name, value)
        for name, value in candidates
        if value is not None and value > SIGNAL_THRESHOLD
    ]
    visible.sort(key=lambda item: item[1], reverse=True)
    return [f"{name} {_fmt_percent(value)}" for name, value in visible[:2]]


def _fmt_percent(value: float) -> str:
    return f"{round(value * 100):.0f}%"
