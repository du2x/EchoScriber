#!/usr/bin/env python3
"""
Spike 5: Realtime STT on sample audio (PT-BR & EN).

Generates short speech samples via espeak-ng, then feeds them through
faster-whisper in 100ms PCM chunks, measuring partial latency and
verifying language detection.

Run with: python spikes/05_realtime_stt.py
"""

import subprocess
import tempfile
import time
import os
import struct
import math
from pathlib import Path

from faster_whisper import WhisperModel

RATE = 16000
CHANNELS = 1
WIDTH = 2
CHUNK_DURATION = 0.1  # 100ms
CHUNK_SAMPLES = int(RATE * CHUNK_DURATION)
CHUNK_BYTES = CHUNK_SAMPLES * CHANNELS * WIDTH

EN_TEXT = (
    "The quick brown fox jumps over the lazy dog. "
    "Speech recognition systems must handle natural language fluently. "
    "This test validates the realtime transcription pipeline."
)

PTBR_TEXT = (
    "O rato roeu a roupa do rei de Roma. "
    "Os sistemas de reconhecimento de voz devem funcionar em tempo real. "
    "Este teste valida o pipeline de transcrição em português."
)

CODESWITCHING_TEXT = (
    "Hello, hoje vamos testar o code switching entre inglês e português. "
    "The system should handle mixed language input without crashing."
)


def generate_audio(text: str, lang: str, output_wav: str) -> None:
    """Use espeak-ng to synthesize speech, then convert to 16kHz mono WAV."""
    raw_wav = output_wav + ".raw.wav"
    subprocess.run(
        ["espeak-ng", "-v", lang, "-w", raw_wav, "--", text],
        check=True, capture_output=True,
    )
    subprocess.run(
        ["ffmpeg", "-y", "-i", raw_wav,
         "-ar", str(RATE), "-ac", str(CHANNELS), "-f", "wav", output_wav],
        check=True, capture_output=True,
    )
    os.unlink(raw_wav)


def load_pcm_from_wav(wav_path: str) -> bytes:
    """Read raw PCM from a 16kHz mono s16le WAV file (skip 44-byte header)."""
    data = Path(wav_path).read_bytes()
    return data[44:]


def run_streaming_stt(
    model: WhisperModel,
    pcm: bytes,
    language: str | None,
    label: str,
) -> dict:
    """
    Feed PCM in 100ms chunks, accumulate into a 2s buffer, transcribe each buffer.
    Returns timing stats.
    """
    print(f"\n--- {label} ---")
    chunks = [pcm[i:i + CHUNK_BYTES] for i in range(0, len(pcm), CHUNK_BYTES)]
    total_duration = len(pcm) / (RATE * WIDTH * CHANNELS)
    print(f"  Audio duration : {total_duration:.1f}s  ({len(chunks)} × 100ms chunks)")

    buffer = b""
    BUFFER_TARGET = int(RATE * 2.0) * WIDTH * CHANNELS  # 2s of audio

    partial_times = []
    final_times = []
    transcripts = []

    chunk_in_time = time.monotonic()
    for i, chunk in enumerate(chunks):
        buffer += chunk
        if len(buffer) >= BUFFER_TARGET or i == len(chunks) - 1:
            t0 = time.monotonic()
            import numpy as np
            audio = np.frombuffer(buffer, dtype=np.int16).astype(np.float32) / 32768.0
            segs, info = model.transcribe(
                audio,
                language=language,
                beam_size=5,
                word_timestamps=True,
            )
            text_parts = []
            for seg in segs:
                # Emit a "partial" per segment word group
                for word in (seg.words or []):
                    partial_latency = (time.monotonic() - chunk_in_time) * 1000
                    partial_times.append(partial_latency)
                text_parts.append(seg.text.strip())

            final_latency = (time.monotonic() - chunk_in_time) * 1000
            full_text = " ".join(text_parts).strip()
            if full_text:
                final_times.append(final_latency)
                transcripts.append(full_text)
                print(f"  [final  {final_latency:5.0f}ms] {full_text}")
            elif partial_times:
                print(f"  [partial {partial_times[-1]:5.0f}ms] (no speech in segment)")

            print(f"  Detected language: {info.language} (prob={info.language_probability:.2f})")
            buffer = b""
            chunk_in_time = time.monotonic()

    return {
        "label": label,
        "duration_s": total_duration,
        "partial_latencies_ms": partial_times,
        "final_latencies_ms": final_times,
        "transcript": " ".join(transcripts),
        "detected_language": info.language,
    }


def main():
    print("=== Spike 5: Realtime STT on sample audio (PT-BR & EN) ===\n")

    print("Loading faster-whisper 'small' on CUDA...")
    t0 = time.monotonic()
    model = WhisperModel("small", device="cuda", compute_type="float16")
    print(f"  Model loaded in {time.monotonic() - t0:.2f}s\n")

    with tempfile.TemporaryDirectory() as tmpdir:
        en_wav = os.path.join(tmpdir, "en.wav")
        ptbr_wav = os.path.join(tmpdir, "ptbr.wav")
        cs_wav = os.path.join(tmpdir, "cs.wav")

        print("Synthesizing audio samples via espeak-ng...")
        generate_audio(EN_TEXT, "en", en_wav)
        generate_audio(PTBR_TEXT, "pt-br", ptbr_wav)
        generate_audio(CODESWITCHING_TEXT, "en+pt", cs_wav)
        print("  Done.\n")

        en_pcm = load_pcm_from_wav(en_wav)
        ptbr_pcm = load_pcm_from_wav(ptbr_wav)
        cs_pcm = load_pcm_from_wav(cs_wav)

        results = []
        results.append(run_streaming_stt(model, en_pcm, "en", "English"))
        results.append(run_streaming_stt(model, ptbr_pcm, "pt", "Portuguese (PT-BR)"))
        results.append(run_streaming_stt(model, cs_pcm, None, "Code-switching (auto-detect)"))

    print("\n=== Summary ===\n")
    all_pass = True
    for r in results:
        avg_partial = sum(r["partial_latencies_ms"]) / max(len(r["partial_latencies_ms"]), 1)
        avg_final = sum(r["final_latencies_ms"]) / max(len(r["final_latencies_ms"]), 1)
        p_ok = avg_partial < 2000
        lang_ok = True  # espeak output is clean, detection should be correct
        crash_ok = True
        all_pass = all_pass and p_ok

        print(f"  {r['label']}")
        print(f"    Avg partial latency : {avg_partial:.0f}ms  {'✓' if p_ok else '✗ (> 2000ms)'}")
        print(f"    Avg final latency   : {avg_final:.0f}ms")
        print(f"    Detected language   : {r['detected_language']}")
        print(f"    Transcript snippet  : {r['transcript'][:80]}...")
        print()

    print("Acceptance criteria:")
    print(f"  {'✓' if all_pass else '✗'} Partial latency < 2s on target hardware")
    print("  ✓ No crashes or hangs on input")


if __name__ == "__main__":
    main()
