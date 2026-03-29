#!/usr/bin/env python3
"""
Spike 2: Mic capture → RMS audio levels via parec (PulseAudio/PipeWire).

Captures mic for 5 seconds and prints RMS per 100ms frame to confirm data flow.
Run with: python spikes/02_mic_capture.py
"""

import math
import struct
import subprocess
import sys
import time

# 48kHz, 16-bit signed LE, 1 channel (mono), 100ms frames
RATE = 48000
CHANNELS = 1
WIDTH = 2  # bytes (s16le)
FRAME_DURATION = 0.1  # seconds
FRAME_SAMPLES = int(RATE * FRAME_DURATION)
FRAME_BYTES = FRAME_SAMPLES * CHANNELS * WIDTH
CAPTURE_SECONDS = 5


def rms(pcm_bytes: bytes) -> float:
    samples = struct.unpack(f"<{len(pcm_bytes) // WIDTH}h", pcm_bytes)
    if not samples:
        return 0.0
    mean_sq = sum(s * s for s in samples) / len(samples)
    return math.sqrt(mean_sq)


def db(rms_val: float) -> float:
    if rms_val <= 0:
        return -96.0
    return 20 * math.log10(rms_val / 32768.0)


def capture_mic(source_name: str | None = None):
    cmd = [
        "parec",
        "--format=s16le",
        f"--rate={RATE}",
        f"--channels={CHANNELS}",
        "--latency-msec=100",
    ]
    if source_name:
        cmd += [f"--device={source_name}"]

    print(f"Capturing mic for {CAPTURE_SECONDS}s — speak into the microphone...\n")
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    start = time.monotonic()
    frame_count = 0
    peak_db = -96.0

    try:
        while time.monotonic() - start < CAPTURE_SECONDS:
            chunk = proc.stdout.read(FRAME_BYTES)
            if not chunk:
                break
            level = rms(chunk)
            level_db = db(level)
            peak_db = max(peak_db, level_db)
            bar = "#" * max(0, int((level_db + 60) / 2))
            print(f"  frame {frame_count:03d}  {level_db:+6.1f} dBFS  {bar}")
            frame_count += 1
    except KeyboardInterrupt:
        pass
    finally:
        proc.terminate()
        proc.wait()

    print(f"\n✓ Captured {frame_count} frames ({frame_count * FRAME_DURATION:.1f}s)")
    print(f"  Peak level: {peak_db:+.1f} dBFS")
    if peak_db > -60:
        print("  ✓ Audio signal detected.")
    else:
        print("  ✗ No significant audio — check mic is connected and unmuted.")


if __name__ == "__main__":
    source = sys.argv[1] if len(sys.argv) > 1 else None
    capture_mic(source)
