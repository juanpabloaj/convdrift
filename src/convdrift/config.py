from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import tomllib


DEFAULT_CONFIG_PATH = Path("convdrift.toml")


@dataclass(slots=True)
class TierWeights:
    tier1: float = 0.5
    tier2: float = 0.3
    tier3: float = 0.2


@dataclass(slots=True)
class Tier1MetricWeights:
    tool_error_rate: float = 0.45
    action_mix_score: float = 0.35
    user_message_length_trend_score: float = 0.20


@dataclass(slots=True)
class Tier2MetricWeights:
    lexical_stagnation_index: float = 0.6
    correction_density: float = 0.4


@dataclass(slots=True)
class Thresholds:
    healthy_max: float = 25.0
    mild_max: float = 50.0
    significant_max: float = 75.0


@dataclass(slots=True)
class AnalysisConfig:
    window_size: int = 5
    smoothing_window: int = 3
    lexical_block_count: int = 5
    lexical_ngram_size: int = 3
    output_format: str = "full"


@dataclass(slots=True)
class PatternsConfig:
    corrections: list[str] = field(
        default_factory=lambda: [
            "no",
            "that's wrong",
            "not what i meant",
            "again",
            "i already told you",
            "wrong",
            "still wrong",
            "no es eso",
            "eso esta mal",
            "esta mal",
            "otra vez",
            "ya te dije",
            "no era eso",
        ]
    )


@dataclass(slots=True)
class Config:
    analysis: AnalysisConfig = field(default_factory=AnalysisConfig)
    tier_weights: TierWeights = field(default_factory=TierWeights)
    tier1_weights: Tier1MetricWeights = field(default_factory=Tier1MetricWeights)
    tier2_weights: Tier2MetricWeights = field(default_factory=Tier2MetricWeights)
    thresholds: Thresholds = field(default_factory=Thresholds)
    patterns: PatternsConfig = field(default_factory=PatternsConfig)


def load_config(config_path: str | Path | None = None) -> Config:
    path = _resolve_config_path(config_path)
    config = Config()
    if path is None:
        return config

    data = tomllib.loads(path.read_text(encoding="utf-8"))
    _apply_analysis(config.analysis, data.get("analysis", {}))
    _apply_weights(config, data.get("weights", {}))
    _apply_thresholds(config.thresholds, data.get("thresholds", {}))
    _apply_patterns(config.patterns, data.get("patterns", {}))
    return config


def default_config_text() -> str:
    config = Config()
    corrections = ", ".join(f'"{pattern}"' for pattern in config.patterns.corrections)
    return f"""[analysis]
window_size = {config.analysis.window_size}
smoothing_window = {config.analysis.smoothing_window}
lexical_block_count = {config.analysis.lexical_block_count}
lexical_ngram_size = {config.analysis.lexical_ngram_size}
output_format = "{config.analysis.output_format}"

[weights.tiers]
tier1 = {config.tier_weights.tier1}
tier2 = {config.tier_weights.tier2}
tier3 = {config.tier_weights.tier3}

[weights.tier1]
tool_error_rate = {config.tier1_weights.tool_error_rate}
action_mix_score = {config.tier1_weights.action_mix_score}
user_message_length_trend_score = {config.tier1_weights.user_message_length_trend_score}

[weights.tier2]
lexical_stagnation_index = {config.tier2_weights.lexical_stagnation_index}
correction_density = {config.tier2_weights.correction_density}

[thresholds]
healthy_max = {config.thresholds.healthy_max}
mild_max = {config.thresholds.mild_max}
significant_max = {config.thresholds.significant_max}

[patterns]
corrections = [{corrections}]
"""


def _resolve_config_path(config_path: str | Path | None) -> Path | None:
    if config_path is not None:
        return Path(config_path)
    if DEFAULT_CONFIG_PATH.exists():
        return DEFAULT_CONFIG_PATH
    return None


def _apply_analysis(config: AnalysisConfig, data: dict[str, Any]) -> None:
    config.window_size = int(data.get("window_size", config.window_size))
    config.smoothing_window = int(data.get("smoothing_window", config.smoothing_window))
    config.lexical_block_count = int(
        data.get("lexical_block_count", config.lexical_block_count)
    )
    config.lexical_ngram_size = int(
        data.get("lexical_ngram_size", config.lexical_ngram_size)
    )
    config.output_format = str(data.get("output_format", config.output_format))


def _apply_weights(config: Config, data: dict[str, Any]) -> None:
    tier_data = data.get("tiers", {})
    config.tier_weights.tier1 = float(tier_data.get("tier1", config.tier_weights.tier1))
    config.tier_weights.tier2 = float(tier_data.get("tier2", config.tier_weights.tier2))
    config.tier_weights.tier3 = float(tier_data.get("tier3", config.tier_weights.tier3))

    tier1_data = data.get("tier1", {})
    config.tier1_weights.tool_error_rate = float(
        tier1_data.get("tool_error_rate", config.tier1_weights.tool_error_rate)
    )
    config.tier1_weights.action_mix_score = float(
        tier1_data.get("action_mix_score", config.tier1_weights.action_mix_score)
    )
    config.tier1_weights.user_message_length_trend_score = float(
        tier1_data.get(
            "user_message_length_trend_score",
            config.tier1_weights.user_message_length_trend_score,
        )
    )

    tier2_data = data.get("tier2", {})
    config.tier2_weights.lexical_stagnation_index = float(
        tier2_data.get(
            "lexical_stagnation_index",
            config.tier2_weights.lexical_stagnation_index,
        )
    )
    config.tier2_weights.correction_density = float(
        tier2_data.get("correction_density", config.tier2_weights.correction_density)
    )


def _apply_thresholds(config: Thresholds, data: dict[str, Any]) -> None:
    config.healthy_max = float(data.get("healthy_max", config.healthy_max))
    config.mild_max = float(data.get("mild_max", config.mild_max))
    config.significant_max = float(data.get("significant_max", config.significant_max))


def _apply_patterns(config: PatternsConfig, data: dict[str, Any]) -> None:
    corrections = data.get("corrections")
    if isinstance(corrections, list):
        config.corrections = [str(pattern) for pattern in corrections]
