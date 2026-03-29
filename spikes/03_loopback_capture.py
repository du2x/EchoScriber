#!/usr/bin/env python3
"""
Spike 3: Loopback (system monitor) capture → RMS audio levels via parec.

Captures the system playback monitor for 5 seconds. Play some audio while running.
Run with: python spikes/03_loopback_capture.py
"""

import math
import struct
import subprocess
import sys
import time

import pulsectl

RATE = 48000
CHANNELS = 2  # monitors are stereo
WIDTH = 2
FRAME_DURATION = 0.1
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


def find_monitor_source() -> str | None:
    with pulsectl.Pulse("echoscriber-spike") as pulse:
        for s in pulse.source_list():
            if s.name.endswith(".monitor"):
                return s.name
    return None


def capture_loopback(source_name: str | None = None):
    if source_name is None:
        source_name = find_monitor_source()
    if source_name is None:
        print("✗ No monitor source found. Cannot capture system playback.")
        sys.exit(1)

    print(f"Monitor source: {source_name}")
    print(f"Capturing system playback for {CAPTURE_SECONDS}s — play some audio...\n")

    cmd = [
        "parec",
        "--format=s16le",
        f"--rate={RATE}",
        f"--channels={CHANNELS}",
        "--latency-msec=100",
        f"--device={source_name}",
    ]
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
        print("  ✓ System audio detected in loopback.")
    else:
        print("  ✗ No audio — ensure something is playing on speakers/headphones.")


if __name__ == "__main__":
    source = sys.argv[1] if len(sys.argv) > 1 else None
    capture_loopback(source)
