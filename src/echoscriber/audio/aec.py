from __future__ import annotations

import subprocess


def is_available() -> bool:
    """Check whether pactl is present (module support verified on actual load)."""
    try:
        subprocess.run(["pactl", "info"], capture_output=True, timeout=5, check=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False


def enable_aec(mic_source: str, monitor_source: str) -> tuple[str, int]:
    """
    Load module-echo-cancel for the given mic/monitor pair.

    Returns (virtual_source_name, module_id).
    Raises RuntimeError if the module cannot be loaded.
    """
    result = subprocess.run(
        [
            "pactl", "load-module", "module-echo-cancel",
            f"source_master={mic_source}",
            f"sink_master={monitor_source}",
            "aec_method=webrtc",
            "source_name=echoscriber_aec",
            "source_properties=device.description=EchoScriber\\ AEC",
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to load module-echo-cancel: {result.stderr.strip()}")
    module_id = int(result.stdout.strip())
    return "echoscriber_aec", module_id


def disable_aec(module_id: int) -> None:
    """Unload the echo-cancel module. Silently ignores errors (module may already be gone)."""
    subprocess.run(
        ["pactl", "unload-module", str(module_id)],
        capture_output=True,
        timeout=5,
    )
