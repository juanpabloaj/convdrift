from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

from watchfiles import Change, watch

from .models import Message, ToolCall, ToolResult, Usage


def read_jsonl(
    transcript_path: str | Path,
    *,
    follow: bool = False,
) -> Iterator[dict[str, Any]]:
    path = Path(transcript_path)
    with path.open("r", encoding="utf-8") as handle:
        watcher = watch(path.parent, recursive=False) if follow else None
        while True:
            line = handle.readline()
            if line:
                yield json.loads(line)
                continue
            if not follow:
                break
            assert watcher is not None
            changes = next(watcher)
            if _transcript_was_updated(changes, path):
                continue


def parse_message(payload: dict[str, Any]) -> Message:
    record = payload.get("message", payload)
    role = _pick_first(record, payload, keys=("role", "type")) or "unknown"
    content = record.get("content", payload.get("content"))
    usage = _parse_usage(_pick_first(record, payload, keys=("usage",)))

    text_blocks: list[str] = []
    tool_calls: list[ToolCall] = []
    tool_results: list[ToolResult] = []

    if isinstance(content, str):
        text_blocks.append(content)
    elif isinstance(content, list):
        for block in content:
            if not isinstance(block, dict):
                continue
            block_type = block.get("type", "")
            if block_type in {"text", "input_text"}:
                text = block.get("text")
                if isinstance(text, str) and text.strip():
                    text_blocks.append(text)
            elif block_type == "tool_use":
                tool_calls.append(
                    ToolCall(
                        name=str(block.get("name", "unknown")),
                        input=_safe_dict(block.get("input")),
                    )
                )
            elif block_type == "tool_result":
                tool_results.append(
                    ToolResult(
                        tool_use_id=_coerce_str(block.get("tool_use_id")),
                        is_error=bool(block.get("is_error", False)),
                        content=_tool_result_text(block.get("content")),
                    )
                )

    is_sidechain = bool(
        payload.get("isSidechain")
        or record.get("isSidechain")
        or payload.get("is_sidechain")
        or record.get("is_sidechain")
    )
    agent_id = _coerce_str(
        payload.get("agentId")
        or record.get("agentId")
        or payload.get("agent_id")
        or record.get("agent_id")
    )

    return Message(
        uuid=_coerce_str(_pick_first(record, payload, keys=("uuid", "id"))),
        parent_uuid=_coerce_str(
            _pick_first(record, payload, keys=("parentUuid", "parent_uuid"))
        ),
        timestamp=_parse_timestamp(
            _pick_first(
                record,
                payload,
                keys=("timestamp", "createdAt", "created_at"),
            )
        ),
        role=role,
        message_kind=_classify_message_kind(
            role=role,
            text_blocks=text_blocks,
            tool_calls=tool_calls,
            tool_results=tool_results,
        ),
        usage=usage,
        text_blocks=text_blocks,
        tool_calls=tool_calls,
        tool_results=tool_results,
        is_sidechain=is_sidechain,
        agent_id=agent_id,
        raw=payload,
    )


def load_messages(transcript_path: str | Path) -> list[Message]:
    return [parse_message(payload) for payload in read_jsonl(transcript_path)]


def _pick_first(*sources: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for source in sources:
        for key in keys:
            if key in source and source[key] is not None:
                return source[key]
    return None


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _safe_dict(value: Any) -> dict[str, Any] | None:
    return value if isinstance(value, dict) else None


def _parse_usage(value: Any) -> Usage | None:
    if not isinstance(value, dict):
        return None
    return Usage(
        input_tokens=_coerce_int(value.get("input_tokens")),
        output_tokens=_coerce_int(value.get("output_tokens")),
        cache_read_input_tokens=_coerce_int(value.get("cache_read_input_tokens")),
        cache_creation_input_tokens=_coerce_int(
            value.get("cache_creation_input_tokens")
        ),
    )


def _tool_result_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "\n".join(parts).strip()
    return ""


def _coerce_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _transcript_was_updated(
    changes: set[tuple[Change, str]], transcript_path: Path
) -> bool:
    for change, changed_path in changes:
        if Path(changed_path) != transcript_path:
            continue
        if change in {Change.added, Change.modified}:
            return True
    return False


def _classify_message_kind(
    *,
    role: str,
    text_blocks: list[str],
    tool_calls: list[ToolCall],
    tool_results: list[ToolResult],
) -> str:
    if role == "system":
        return "system"
    if role == "assistant" and tool_calls:
        return "assistant_tool_use"
    if role == "user" and tool_results and not text_blocks:
        return "tool_result"
    if role == "user" and text_blocks:
        return "human"
    if role == "assistant" and text_blocks:
        return "assistant_text"
    return "other"
