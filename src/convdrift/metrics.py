from __future__ import annotations

import re
from dataclasses import dataclass
from collections import Counter
from typing import Iterable

from .config import Config
from .models import Episode, Message, ToolCall


PRODUCTIVE_TOOLS = {"write", "edit", "notebookedit", "multiedit"}
EXPLORATORY_TOOLS = {"read", "glob", "grep", "ls"}
RECURSIVE_TOOLS = {"agent", "task"}
READ_ONLY_BASH_PREFIXES = {
    "cat",
    "find",
    "git diff",
    "git log",
    "git show",
    "head",
    "less",
    "ls",
    "pwd",
    "rg",
    "sed",
    "sort",
    "tail",
}
WRITE_BASH_PREFIXES = {
    "cp",
    "git apply",
    "mkdir",
    "mv",
    "tee",
    "touch",
}


@dataclass(slots=True)
class ActionMix:
    productive: float
    exploratory: float
    recursive: float


@dataclass(slots=True)
class Tier1Metrics:
    tool_error_rate: float
    action_mix: ActionMix
    action_mix_score: float
    user_message_length_slope: float
    user_message_length_trend_score: float
    token_asymmetry_ratio: float | None
    cache_efficiency_drop: float | None


@dataclass(slots=True)
class Tier2Metrics:
    lexical_stagnation_index: float
    correction_density: float


def compute_tier1_metrics(
    episodes: list[Episode], *, config: Config | None = None
) -> Tier1Metrics:
    """Compute Tier 1 metrics for a window of episodes.

    `action_mix_score` is a derived drift signal, not the neutral distribution itself.
    It measures non-productive pressure as `exploratory + recursive`.
    """

    tool_results = [
        tool_result
        for episode in episodes
        for message in episode.messages
        for tool_result in message.tool_results
    ]
    total_tool_results = len(tool_results)
    tool_error_rate = (
        sum(1 for tool_result in tool_results if tool_result.is_error)
        / total_tool_results
        if total_tool_results
        else 0.0
    )

    action_mix = _compute_action_mix(
        tool_call
        for episode in episodes
        for message in episode.messages
        for tool_call in message.tool_calls
    )
    # This is intentionally a drift-oriented score, not the raw action mix ratio.
    action_mix_score = min(1.0, action_mix.exploratory + action_mix.recursive)

    user_lengths = [len(episode.user_message.text.split()) for episode in episodes]
    user_message_length_slope = _linear_slope(user_lengths)
    average_length = sum(user_lengths) / len(user_lengths) if user_lengths else 0.0
    user_message_length_trend_score = _normalize_positive_trend(
        user_message_length_slope,
        average_length,
    )

    assistant_messages = [
        message
        for episode in episodes
        for message in episode.messages
        if message.role == "assistant"
    ]
    token_asymmetry_ratio = _compute_token_asymmetry_ratio(assistant_messages)
    cache_efficiency_drop = _compute_cache_efficiency_drop(assistant_messages)

    return Tier1Metrics(
        tool_error_rate=tool_error_rate,
        action_mix=action_mix,
        action_mix_score=action_mix_score,
        user_message_length_slope=user_message_length_slope,
        user_message_length_trend_score=user_message_length_trend_score,
        token_asymmetry_ratio=token_asymmetry_ratio,
        cache_efficiency_drop=cache_efficiency_drop,
    )


def _compute_action_mix(tool_calls: Iterable[ToolCall]) -> ActionMix:
    productive = 0
    exploratory = 0
    recursive = 0

    for tool_call in tool_calls:
        category = _classify_tool_call(tool_call)
        if category == "productive":
            productive += 1
        elif category == "exploratory":
            exploratory += 1
        elif category == "recursive":
            recursive += 1

    total = productive + exploratory + recursive
    if total == 0:
        return ActionMix(productive=0.0, exploratory=0.0, recursive=0.0)

    return ActionMix(
        productive=productive / total,
        exploratory=exploratory / total,
        recursive=recursive / total,
    )


def _classify_tool_call(tool_call: ToolCall) -> str:
    tool_name = tool_call.name.strip().lower()
    if tool_name in PRODUCTIVE_TOOLS:
        return "productive"
    if tool_name in EXPLORATORY_TOOLS:
        return "exploratory"
    if tool_name in RECURSIVE_TOOLS:
        return "recursive"
    if tool_name == "bash":
        return _classify_bash_call(tool_call)
    return "exploratory"


def _classify_bash_call(tool_call: ToolCall) -> str:
    command = ""
    if tool_call.input:
        raw_command = tool_call.input.get("command") or tool_call.input.get("cmd")
        if isinstance(raw_command, str):
            command = raw_command.strip().lower()

    if any(command.startswith(prefix) for prefix in READ_ONLY_BASH_PREFIXES):
        return "exploratory"
    if any(command.startswith(prefix) for prefix in WRITE_BASH_PREFIXES):
        return "productive"
    if any(token in command for token in (">", ">>")):
        return "productive"
    return "exploratory"


def _linear_slope(values: list[int]) -> float:
    if len(values) < 2:
        return 0.0

    x_values = list(range(len(values)))
    mean_x = sum(x_values) / len(x_values)
    mean_y = sum(values) / len(values)

    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(x_values, values))
    denominator = sum((x - mean_x) ** 2 for x in x_values)
    if denominator == 0:
        return 0.0
    return numerator / denominator


def _normalize_positive_trend(slope: float, average_length: float) -> float:
    if slope <= 0:
        return 0.0
    baseline = max(average_length, 1.0)
    return min(1.0, slope / baseline)


def _compute_token_asymmetry_ratio(messages: list[Message]) -> float | None:
    ratios: list[float] = []
    for message in messages:
        if message.usage is None:
            continue
        input_tokens = message.usage.input_tokens or 0
        cache_read_tokens = message.usage.cache_read_input_tokens or 0
        denominator = input_tokens + cache_read_tokens
        if denominator <= 0:
            continue
        output_tokens = message.usage.output_tokens or 0
        ratios.append(output_tokens / denominator)
    if not ratios:
        return None
    return sum(ratios) / len(ratios)


def _compute_cache_efficiency_drop(messages: list[Message]) -> float | None:
    efficiencies: list[float] = []
    for message in messages:
        if message.usage is None:
            continue
        input_tokens = message.usage.input_tokens or 0
        cache_read_tokens = message.usage.cache_read_input_tokens or 0
        cache_creation_tokens = message.usage.cache_creation_input_tokens or 0
        denominator = input_tokens + cache_read_tokens + cache_creation_tokens
        if denominator <= 0:
            continue
        efficiencies.append(cache_read_tokens / denominator)

    if not efficiencies:
        return None
    if len(efficiencies) == 1:
        return 0.0

    baseline = sum(efficiencies[:-1]) / len(efficiencies[:-1])
    latest = efficiencies[-1]
    return max(0.0, baseline - latest)


def compute_tier2_metrics(episodes: list[Episode], *, config: Config) -> Tier2Metrics:
    assistant_blocks = [
        message.text
        for episode in episodes
        for message in episode.messages
        if message.role == "assistant" and message.text
    ]
    user_messages = [
        episode.user_message.text for episode in episodes if episode.user_message.text
    ]

    lexical_stagnation_index = _compute_lexical_stagnation_index(
        assistant_blocks,
        block_count=config.analysis.lexical_block_count,
        ngram_size=config.analysis.lexical_ngram_size,
    )
    correction_density = _compute_correction_density(
        user_messages,
        patterns=config.patterns.corrections,
    )
    return Tier2Metrics(
        lexical_stagnation_index=lexical_stagnation_index,
        correction_density=correction_density,
    )


def _compute_lexical_stagnation_index(
    assistant_blocks: list[str], *, block_count: int, ngram_size: int
) -> float:
    recent_blocks = assistant_blocks[-block_count:]
    if len(recent_blocks) < 2:
        return 0.0

    overlap_scores: list[float] = []
    previous_ngrams = _extract_ngrams(recent_blocks[0], ngram_size)
    for block in recent_blocks[1:]:
        current_ngrams = _extract_ngrams(block, ngram_size)
        if not previous_ngrams or not current_ngrams:
            overlap_scores.append(0.0)
        else:
            shared = sum((previous_ngrams & current_ngrams).values())
            total = min(sum(previous_ngrams.values()), sum(current_ngrams.values()))
            overlap_scores.append(shared / total if total else 0.0)
        previous_ngrams = current_ngrams

    if not overlap_scores:
        return 0.0
    return sum(overlap_scores) / len(overlap_scores)


def _extract_ngrams(text: str, ngram_size: int) -> Counter[tuple[str, ...]]:
    tokens = re.findall(r"[a-z0-9_]+", text.lower())
    if len(tokens) < ngram_size:
        return Counter()
    return Counter(
        tuple(tokens[index : index + ngram_size])
        for index in range(len(tokens) - ngram_size + 1)
    )


def _compute_correction_density(
    user_messages: list[str], *, patterns: list[str]
) -> float:
    if not user_messages:
        return 0.0

    pattern_hits = 0
    lowered_patterns = [pattern.lower() for pattern in patterns]
    for message in user_messages:
        lowered = message.lower()
        if any(pattern in lowered for pattern in lowered_patterns):
            pattern_hits += 1

    return pattern_hits / len(user_messages)
