from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol


class SourceMode(str, Enum):
    MIC = "Mic"
    SYSTEM = "System"
    BOTH = "Both"


class SegmentSource(str, Enum):
    MIC = "MIC"
    SYSTEM = "SYSTEM"


class AgentMode(str, Enum):
    SUMMARY = "Summary"
    DECISIONS = "Key Decisions"
    ACTIONS = "Action Items"
    QA = "Q&A"
    EXPLAIN = "Explain"

    @property
    def needs_prompt(self) -> bool:
        return self in (AgentMode.QA, AgentMode.EXPLAIN)


@dataclass(slots=True)
class TranscriptSegment:
    text: str
    source: SegmentSource
    is_final: bool
    timestamp: float = field(default_factory=time.time)


@dataclass(slots=True)
class AgentResult:
    mode: AgentMode
    query: str | None
    response: str
    timestamp: float = field(default_factory=time.time)


class STTEngine(Protocol):
    def start(self) -> None:
        ...

    def stop(self) -> None:
        ...

    def push_audio(self, chunk: bytes, source_id: SegmentSource) -> None:
        ...

    def list_models(self) -> list[str]:
        ...
