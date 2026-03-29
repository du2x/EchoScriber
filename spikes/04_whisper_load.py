#!/usr/bin/env python3
"""
Spike 4: faster-whisper model load & warmup latency benchmark.

Tests GPU first, falls back to CPU if CUDA is unavailable.
Run with: python spikes/04_whisper_load.py [model_size]
  model_size: tiny, base, small (default: tiny)
"""

import sys
import time
import tempfile
import struct
import math

from faster_whisper import WhisperModel

MODEL = sys.argv[1] if len(sys.argv) > 1 else "tiny"


def try_device(device: str, compute_type: str) -> WhisperModel | None:
    try:
        print(f"  Loading '{MODEL}' on {device} ({compute_type})...", end=" ", flush=True)
        t0 = time.monotonic()
        model = WhisperModel(MODEL, device=device, compute_type=compute_type)
        elapsed = time.monotonic() - t0
        print(f"{elapsed:.2f}s")
        return model, elapsed
    except Exception as e:
        print(f"failed ({e})")
        return None, None


def make_silence_wav(duration_s: float = 1.0, rate: int = 16000) -> str:
    """Write a minimal WAV file with silence for warmup inference."""
    n_samples = int(rate * duration_s)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        # WAV header
        data_size = n_samples * 2
        f.write(b"RIFF")
        f.write(struct.pack("<I", 36 + data_size))
        f.write(b"WAVEfmt ")
        f.write(struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16))
        f.write(b"data")
        f.write(struct.pack("<I", data_size))
        f.write(b"\x00" * data_size)
        return f.name


def warmup(model: WhisperModel, wav_path: str) -> float:
    print("  Running warmup inference...", end=" ", flush=True)
    t0 = time.monotonic()
    segments, info = model.transcribe(wav_path, language="en", beam_size=1)
    list(segments)  # consume generator
    elapsed = time.monotonic() - t0
    print(f"{elapsed:.2f}s  (detected language: {info.language})")
    return elapsed


if __name__ == "__main__":
    print(f"=== faster-whisper load & warmup (model={MODEL}) ===\n")

    model = None
    load_time = None

    import torch
    has_cuda = torch.cuda.is_available()

    if has_cuda:
        print("Trying CUDA GPU:")
        model, load_time = try_device("cuda", "float16")
    else:
        print("CUDA not available — skipping GPU test.")

    if model is None:
        print("Trying CPU (int8):")
        model, load_time = try_device("cpu", "int8")

    if model is None:
        print("✗ Could not load model on any device.")
        sys.exit(1)

    wav = make_silence_wav()
    warmup_time = warmup(model, wav)

    print(f"\n=== Results ===")
    print(f"  Model load time : {load_time:.2f}s")
    print(f"  Warmup inference: {warmup_time:.2f}s")
    print(f"  Total startup   : {load_time + warmup_time:.2f}s")

    if load_time + warmup_time < 10:
        print("\n✓ Startup time is acceptable (< 10s).")
    else:
        print("\n⚠ Startup is slow — consider GPU or a smaller model.")
