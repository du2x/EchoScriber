from __future__ import annotations

import logging
import math
import struct
import time

from PySide6.QtCore import QObject, Signal

from .audio.aec import disable_aec, enable_aec, is_available as aec_available
from .audio.capture import CaptureWorker, LoopbackCapture, MicCapture
from .models import SegmentSource, SourceMode, TranscriptSegment
from .services import SessionConfig
from .transcript_store import TranscriptStore

logger = logging.getLogger(__name__)


class SessionController(QObject):
    """
    Real pipeline that replaces MockRealtimePipeline.

    Emits the same signals as the mock so gui.py needs no structural changes.
    Additional signals: error(str) and metrics_updated(latency_ms, rms_db).

    State machine: idle → loading_model → running → stopping → idle
    """

    partial_emitted = Signal(TranscriptSegment)
    final_emitted = Signal(TranscriptSegment)
    status_changed = Signal(str)
    error = Signal(str)
    metrics_updated = Signal(int, float)  # latency_ms, rms_db

    def __init__(self) -> None:
        super().__init__()
        self._mic_worker: CaptureWorker | None = None
        self._loopback_worker: CaptureWorker | None = None
        self._stt = None
        self._aec_module_id: int | None = None
        self._segment_start: float = 0.0
        self._last_rms_db: float = -96.0
        self.store = TranscriptStore()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self, config: SessionConfig) -> None:
        self.status_changed.emit("Loading model…")

        stt = self._build_stt(config)
        stt.set_segment_callback(self._on_segment)
        stt.start()
        self._stt = stt
        self._segment_start = time.monotonic()

        mic_source = config.mic_device if config.mic_device != "Default Microphone" else None

        if config.echo_cancellation and aec_available():
            monitor = config.monitor_device if config.monitor_device != "Default Monitor" else None
            if mic_source and monitor:
                try:
                    aec_src, self._aec_module_id = enable_aec(mic_source, monitor)
                    mic_source = aec_src
                    logger.info("AEC enabled (module %d)", self._aec_module_id)
                except RuntimeError as exc:
                    logger.warning("AEC unavailable: %s", exc)

        if config.source_mode in (SourceMode.MIC, SourceMode.BOTH):
            self._mic_worker = MicCapture(device=mic_source)
            self._mic_worker.pcm_ready.connect(
                lambda data: self._on_pcm(data, SegmentSource.MIC)
            )
            self._mic_worker.error.connect(self._on_worker_error)
            self._mic_worker.start()

        if config.source_mode in (SourceMode.SYSTEM, SourceMode.BOTH):
            monitor = config.monitor_device if config.monitor_device != "Default Monitor" else None
            self._loopback_worker = LoopbackCapture(device=monitor)
            self._loopback_worker.pcm_ready.connect(
                lambda data: self._on_pcm(data, SegmentSource.SYSTEM)
            )
            self._loopback_worker.error.connect(self._on_worker_error)
            self._loopback_worker.start()

        self.status_changed.emit("Running")

    def stop(self) -> None:
        self.status_changed.emit("Stopping…")
        self._stop_workers()
        if self._stt is not None:
            self._stt.stop()
            self._stt = None
        if self._aec_module_id is not None:
            disable_aec(self._aec_module_id)
            self._aec_module_id = None
        self.status_changed.emit("Stopped")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _build_stt(self, config: SessionConfig):
        if config.stt_backend == "huggingface":
            from .stt.hf_adapter import HuggingFaceAdapter
            return HuggingFaceAdapter(model_id=config.model, language=config.language)
        from .stt.whisper_adapter import WhisperAdapter
        return WhisperAdapter(model_id=config.model, language=config.language)

    def _stop_workers(self) -> None:
        for worker in (self._mic_worker, self._loopback_worker):
            if worker is not None:
                worker.stop()
                worker.wait(2000)
        self._mic_worker = None
        self._loopback_worker = None

    def _on_pcm(self, data: bytes, source: SegmentSource) -> None:
        if self._stt is not None:
            self._last_rms_db = self._rms_db(data)
            self._segment_start = time.monotonic()
            self._stt.push_audio(data, source)

    def _on_segment(self, segment: TranscriptSegment) -> None:
        latency_ms = int((time.monotonic() - self._segment_start) * 1000)
        if segment.is_final:
            self.store.append(segment)
            self.final_emitted.emit(segment)
            self.metrics_updated.emit(latency_ms, self._last_rms_db)
        else:
            self.partial_emitted.emit(segment)

    @staticmethod
    def _rms_db(data: bytes) -> float:
        n = len(data) // 2
        if n == 0:
            return -96.0
        samples = struct.unpack(f"<{n}h", data[:n * 2])
        mean_sq = sum(s * s for s in samples) / n
        if mean_sq <= 0:
            return -96.0
        return 20.0 * math.log10(math.sqrt(mean_sq) / 32768.0)

    def _on_worker_error(self, message: str) -> None:
        logger.error("Capture error: %s", message)
        self._stop_workers()
        if self._stt is not None:
            self._stt.stop()
            self._stt = None
        if self._aec_module_id is not None:
            disable_aec(self._aec_module_id)
            self._aec_module_id = None
        self.error.emit(message)
        self.status_changed.emit("Error")
