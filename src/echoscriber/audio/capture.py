from __future__ import annotations

import subprocess

from PySide6.QtCore import QThread, Signal

# 16 kHz mono s16le — compatible with faster-whisper input
RATE = 16000
CHANNELS = 1
WIDTH = 2  # bytes per sample (s16le)
FRAME_DURATION = 0.1  # seconds
FRAME_SAMPLES = int(RATE * FRAME_DURATION)
FRAME_BYTES = FRAME_SAMPLES * CHANNELS * WIDTH


class CaptureWorker(QThread):
    pcm_ready = Signal(bytes)
    error = Signal(str)

    def __init__(self, device: str | None = None) -> None:
        super().__init__()
        self._device = device
        self._running = False

    def _build_cmd(self) -> list[str]:
        raise NotImplementedError

    def run(self) -> None:
        cmd = self._build_cmd()
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except FileNotFoundError:
            self.error.emit("parec not found — install pulseaudio-utils")
            return

        self._running = True
        try:
            while self._running:
                chunk = proc.stdout.read(FRAME_BYTES)
                if not chunk:
                    if self._running:
                        self.error.emit("Audio stream ended unexpectedly")
                    break
                self.pcm_ready.emit(bytes(chunk))
        finally:
            self._running = False
            proc.terminate()
            try:
                proc.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                proc.kill()

    def stop(self) -> None:
        self._running = False


class MicCapture(CaptureWorker):
    def _build_cmd(self) -> list[str]:
        cmd = [
            "parec",
            "--format=s16le",
            f"--rate={RATE}",
            f"--channels={CHANNELS}",
            "--latency-msec=100",
        ]
        if self._device:
            cmd.append(f"--device={self._device}")
        return cmd


class LoopbackCapture(CaptureWorker):
    def _build_cmd(self) -> list[str]:
        cmd = [
            "parec",
            "--format=s16le",
            f"--rate={RATE}",
            f"--channels={CHANNELS}",
            "--latency-msec=100",
        ]
        if self._device:
            cmd.append(f"--device={self._device}")
        return cmd
