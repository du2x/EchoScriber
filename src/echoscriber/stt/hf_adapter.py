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


class HuggingFaceAdapter:
    """
    STTEngine adapter backed by transformers ASR pipeline.

    Targets PT-BR fine-tuned Whisper models on HuggingFace Hub that have
    not yet been converted to CTranslate2 format. Falls back to GPU if
    available, otherwise CPU.
    """

    def __init__(
        self,
        model_id: str = "openai/whisper-small",
        language: str | None = None,
    ) -> None:
        self._model_id = model_id
        self._language = language
        self._pipeline = None
        self._queue: queue.Queue[tuple[bytes, SegmentSource] | None] = queue.Queue(maxsize=50)
        self._thread: threading.Thread | None = None
        self._on_segment: Callable[[TranscriptSegment], None] | None = None

    def set_segment_callback(self, callback: Callable[[TranscriptSegment], None]) -> None:
        self._on_segment = callback

    def start(self) -> None:
        from transformers import pipeline as hf_pipeline

        device = 0 if self._cuda_available() else -1
        logger.info("Loading HuggingFace ASR '%s' on device=%d…", self._model_id, device)
        self._pipeline = hf_pipeline(
            "automatic-speech-recognition",
            model=self._model_id,
            device=device,
        )
        logger.info("Model loaded.")

        self._thread = threading.Thread(target=self._run, daemon=True, name="hf-inference")
        self._thread.start()

    def stop(self) -> None:
        self._queue.put(None)
        if self._thread is not None:
            self._thread.join(timeout=10)
            self._thread = None

    def push_audio(self, chunk: bytes, source_id: SegmentSource) -> None:
        try:
            self._queue.put_nowait((chunk, source_id))
        except queue.Full:
            logger.debug("HF STT queue full — dropping audio chunk")

    def list_models(self) -> list[str]:
        return [self._model_id]

    # ------------------------------------------------------------------

    def _cuda_available(self) -> bool:
        try:
            import torch
            return torch.cuda.is_available()
        except ImportError:
            return False

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

        if buffer:
            self._transcribe(buffer, current_source)

    def _transcribe(self, buffer: list[bytes], source: SegmentSource) -> None:
        if self._pipeline is None or self._on_segment is None:
            return

        raw = b"".join(buffer)
        audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0

        generate_kwargs: dict = {}
        if self._language:
            lang = self._language
            if lang == "pt-BR":
                lang = "portuguese"
            elif lang == "en":
                lang = "english"
            generate_kwargs["language"] = lang

        try:
            result = self._pipeline(
                {"sampling_rate": RATE, "raw": audio},
                generate_kwargs=generate_kwargs,
            )
            text = result.get("text", "").strip()
            if text:
                self._on_segment(TranscriptSegment(text=text, source=source, is_final=True))
        except Exception:
            logger.exception("HuggingFace inference error")
