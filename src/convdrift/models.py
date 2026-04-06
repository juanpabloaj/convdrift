from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class ToolCall:
    name: str
    input: dict[str, Any] | None = None


@dataclass(slots=True)
class ToolResult:
    tool_use_id: str | None
    is_error: bool
    content: str = ""


@dataclass(slots=True)
class Usage:
    input_tokens: int | None = None
    output_tokens: int | None = None
    cache_read_input_tokens: int | None = None
    cache_creation_input_tokens: int | None = None


@dataclass(slots=True)
class Message:
    uuid: str | None
    parent_uuid: str | None
    timestamp: datetime | None
    role: str
    message_kind: str
    usage: Usage | None = None
    text_blocks: list[str] = field(default_factory=list)
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_results: list[ToolResult] = field(default_factory=list)
    is_sidechain: bool = False
    agent_id: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def text(self) -> str:
        return "\n".join(block for block in self.text_blocks if block).strip()

    @property
    def is_human_input(self) -> bool:
        if self.role != "user":
            return False
        if self.tool_results and not self.text_blocks:
            return False
        return bool(self.text_blocks)


@dataclass(slots=True)
class Episode:
    chain_id: str
    sequence: int
    user_message: Message
    messages: list[Message] = field(default_factory=list)

    @property
    def message_count(self) -> int:
        return len(self.messages)

    @property
    def message_type_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for message in self.messages:
            counts[message.role] = counts.get(message.role, 0) + 1
        return counts
