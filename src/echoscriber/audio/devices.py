from __future__ import annotations

from dataclasses import dataclass

import pulsectl


@dataclass(slots=True)
class AudioDevice:
    index: int
    name: str
    description: str
    is_monitor: bool
    sample_rate: int
    channels: int


def _pulse_sources() -> list[AudioDevice]:
    devices: list[AudioDevice] = []
    with pulsectl.Pulse("echoscriber") as pulse:
        for s in pulse.source_list():
            devices.append(AudioDevice(
                index=s.index,
                name=s.name,
                description=s.description,
                is_monitor=s.name.endswith(".monitor"),
                sample_rate=s.sample_spec.rate,
                channels=s.sample_spec.channels,
            ))
    return devices


def list_mics() -> list[AudioDevice]:
    return [d for d in _pulse_sources() if not d.is_monitor]


def list_monitors() -> list[AudioDevice]:
    return [d for d in _pulse_sources() if d.is_monitor]


def list_all() -> list[AudioDevice]:
    return _pulse_sources()
