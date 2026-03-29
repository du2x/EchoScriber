from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol


class SourceMode(str, Enum):
    MIC = "Mic"
    SYSTEM = "System"
    BOTH = "Both"


class SegmentSource(str, Enum):
    MIC = "MIC"
    SYSTEM = "SYSTEM"


@dataclass(slots=True)
class TranscriptSegment:
    text: str
    source: SegmentSource
    is_final: bool


class STTEngine(Protocol):
    def start(self) -> None:
        ...

    def stop(self) -> None:
        ...

    def push_audio(self, chunk: bytes, source_id: SegmentSource) -> None:
        ...

    def list_models(self) -> list[str]:
        ...
