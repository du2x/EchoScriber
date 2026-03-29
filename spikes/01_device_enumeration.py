#!/usr/bin/env python3
"""
Spike 1: PipeWire/PulseAudio device enumeration via pulsectl and sounddevice.

Prints all available audio sources (mic inputs and monitor/loopback sources).
Run with: python spikes/01_device_enumeration.py
"""

import pulsectl


def list_pulse_sources():
    print("=== PulseAudio/PipeWire sources (pulsectl) ===\n")
    with pulsectl.Pulse("echoscriber-spike") as pulse:
        sources = pulse.source_list()
        mics = []
        monitors = []
        for s in sources:
            entry = {
                "index": s.index,
                "name": s.name,
                "description": s.description,
                "sample_rate": s.sample_spec.rate,
                "channels": s.sample_spec.channels,
                "state": str(s.state),
            }
            if s.name.endswith(".monitor"):
                monitors.append(entry)
            else:
                mics.append(entry)

        print(f"Microphone inputs ({len(mics)} found):")
        for m in mics:
            print(
                f"  [{m['index']}] {m['description']}\n"
                f"       name={m['name']}\n"
                f"       {m['sample_rate']} Hz, {m['channels']}ch, state={m['state']}"
            )

        print(f"\nMonitor/loopback sources ({len(monitors)} found):")
        for m in monitors:
            print(
                f"  [{m['index']}] {m['description']}\n"
                f"       name={m['name']}\n"
                f"       {m['sample_rate']} Hz, {m['channels']}ch, state={m['state']}"
            )

    return mics, monitors


if __name__ == "__main__":
    mics, monitors = list_pulse_sources()

    print("\n=== Summary ===")
    print(f"{len(mics)} mic(s), {len(monitors)} monitor(s)")

    if monitors:
        print("\n✓ Loopback monitor source available — system playback capture is feasible.")
    else:
        print("\n✗ No monitor source found — check PipeWire/PulseAudio configuration.")
