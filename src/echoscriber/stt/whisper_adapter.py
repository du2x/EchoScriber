from __future__ import annotations

import logging
import queue
import threading
from typing import Callable

import numpy as np

from ..models import SegmentSource, TranscriptSegment

logger = logging.getLogger(__name__)

RATE = 16000
BUFFER_SECONDS = 2.0
BUFFER_SAMPLES = int(RATE * BUFFER_SECONDS)
BUFFER_BYTES = BUFFER_SAMPLES * 2  # s16le


class WhisperAdapter:
    """
    STTEngine adapter backed by faster-whisper.

    Audio is pushed via push_audio() from any thread. A background thread
    accumulates chunks into 2s buffers and runs inference, then calls the
    segment callback with partial and final TranscriptSegments.

    Supports loading standard faster-whisper model sizes ("tiny", "base",
    "small", "medium", "large-v3") as well as HuggingFace Hub model IDs
    that have been converted to CTranslate2 format.
    """

    def __init__(
        self,
        model_id: str = "small",
        device: str = "auto",
        compute_type: str = "default",
        language: str | None = None,
    ) -> None:
        self._model_id = model_id
        self._device = device
        self._compute_type = compute_type
        self._language = language
        self._model = None
        self._queue: queue.Queue[tuple[bytes, SegmentSource] | None] = queue.Queue(maxsize=50)
        self._thread: threading.Thread | None = None
        self._on_segment: Callable[[TranscriptSegment], None] | None = None

    def set_segment_callback(self, callback: Callable[[TranscriptSegment], None]) -> None:
        self._on_segment = callback

    def start(self) -> None:
        device = self._resolve_device()
        compute_type = self._compute_type
        if compute_type == "default":
            compute_type = "float16" if device == "cuda" else "int8"

        from faster_whisper import WhisperModel
        logger.info("Loading faster-whisper '%s' on %s (%s)…", self._model_id, device, compute_type)
        self._model = WhisperModel(self._model_id, device=device, compute_type=compute_type)
        logger.info("Model loaded.")

        self._thread = threading.Thread(target=self._run, daemon=True, name="whisper-inference")
        self._thread.start()

    def stop(self) -> None:
        self._queue.put(None)  # sentinel
        if self._thread is not None:
            self._thread.join(timeout=10)
            self._thread = None

    def push_audio(self, chunk: bytes, source_id: SegmentSource) -> None:
        try:
            self._queue.put_nowait((chunk, source_id))
        except queue.Full:
            logger.debug("STT queue full — dropping audio chunk")

    def list_models(self) -> list[str]:
        return ["tiny", "base", "small", "medium", "large-v2", "large-v3"]

    # ------------------------------------------------------------------

    def _resolve_device(self) -> str:
        if self._device != "auto":
            return self._device
        try:
            import torch
            return "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            return "cpu"

    def _run(self) -> None:
        buffer: list[bytes] = []
        buffer_bytes = 0
        current_source = SegmentSource.MIC

        while True:
            item = self._queue.get()
            if item is None:
                break
            chunk, source = item
            current_source = source
            buffer.append(chunk)
            buffer_bytes += len(chunk)

            if buffer_bytes >= BUFFER_BYTES:
                self._transcribe(buffer, current_source)
                buffer = []
                buffer_bytes = 0

        # Flush remaining audio
        if buffer:
            self._transcribe(buffer, current_source)

    def _transcribe(self, buffer: list[bytes], source: SegmentSource) -> None:
        if self._model is None or self._on_segment is None:
            return

        raw = b"".join(buffer)
        audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0

        lang = self._language
        if lang == "pt-BR":
            lang = "pt"

        try:
            segments, _ = self._model.transcribe(
                audio,
                language=lang,
                beam_size=5,
                word_timestamps=True,
                vad_filter=True,
            )
            full_text = ""
            for seg in segments:
                text = seg.text.strip()
                if not text:
                    continue
                full_text += (" " if full_text else "") + text
                self._on_segment(TranscriptSegment(
                    text=full_text + "…",
                    source=source,
                    is_final=False,
                ))

            if full_text:
                self._on_segment(TranscriptSegment(
                    text=full_text,
                    source=source,
                    is_final=True,
                ))
        except Exception:
            logger.exception("Inference error")
