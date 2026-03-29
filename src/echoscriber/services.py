from __future__ import annotations

from dataclasses import dataclass
from itertools import cycle

from PySide6.QtCore import QObject, QTimer, Signal

from .models import SegmentSource, SourceMode, TranscriptSegment


@dataclass(slots=True)
class SessionConfig:
    source_mode: SourceMode = SourceMode.MIC
    mic_device: str = "Default Microphone"
    monitor_device: str = "Default Monitor"
    echo_cancellation: bool = True
    language: str = "en"
    model: str = "small"


class MockRealtimePipeline(QObject):
    partial_emitted = Signal(TranscriptSegment)
    final_emitted = Signal(TranscriptSegment)
    status_changed = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._timer = QTimer(self)
        self._timer.setInterval(900)
        self._timer.timeout.connect(self._emit_tick)
        self._phrases = cycle(
            [
                "running incremental transcript",
                "echo cancellation reference healthy",
                "gpu path active for model inference",
                "capturing from configured source",
                "session diagnostics normal",
            ]
        )
        self._config = SessionConfig()

    def start(self, config: SessionConfig) -> None:
        self._config = config
        self.status_changed.emit("Running")
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()
        self.status_changed.emit("Stopped")

    def _emit_tick(self) -> None:
        phrase = next(self._phrases)
        for source in self._active_sources():
            self.partial_emitted.emit(
                TranscriptSegment(text=f"{phrase} ...", source=source, is_final=False)
            )
            self.final_emitted.emit(
                TranscriptSegment(text=phrase, source=source, is_final=True)
            )

    def _active_sources(self) -> list[SegmentSource]:
        if self._config.source_mode == SourceMode.MIC:
            return [SegmentSource.MIC]
        if self._config.source_mode == SourceMode.SYSTEM:
            return [SegmentSource.SYSTEM]
        return [SegmentSource.MIC, SegmentSource.SYSTEM]
