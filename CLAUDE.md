# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Setup
python -m venv .venv
source .venv/bin/activate
pip install -e .

# Run the app
echoscriber

# Syntax validation (no test suite yet)
python -m compileall src
```

## Architecture

EchoScriber is a Linux desktop speech-to-text app built with **Python 3.10+ and PySide6 (Qt6)**. The architecture follows Qt's signal/slot pattern across four modules:

- **`app.py`** — Entry point. Creates `QApplication`, instantiates `MainWindow`, runs the Qt event loop.
- **`models.py`** — Data layer: `SourceMode` enum (MIC/SYSTEM/BOTH), `TranscriptSegment` dataclass, and the `STTEngine` Protocol (abstract interface for future STT backends).
- **`services.py`** — Business logic. `SessionConfig` holds user settings. `MockRealtimePipeline` (a `QObject`) simulates realtime transcription by emitting `segment_ready` signals on a timer. Real audio capture and STT are not yet implemented.
- **`gui.py`** — UI layer. `MainWindow` builds all controls, connects pipeline signals to UI slots. Partial transcripts go to the status bar; final segments are timestamped and appended to a `QTextEdit`.

**Control flow:** User clicks Start → `SessionConfig` is built from UI state → `pipeline.start(config)` → timer ticks → signals emitted → UI slots update.

## Current State

This is a **mock scaffold**. The GUI and data models are complete, but the following are not yet implemented:
- Real audio capture (mic or system loopback via PipeWire)
- Echo cancellation (WebRTC AEC)
- Real STT backends (faster-whisper)
- PipeWire device enumeration
- Persistence (settings storage)

The PRD (`PRD.md`) describes the full product vision, technical direction, and prioritized backlog (P0/P1/P2). The planned stack is: **PipeWire** for audio, **faster-whisper** for STT, **WebRTC AEC** for echo cancellation, with GPU inference support. Languages targeted are Portuguese (Brazil) and English.
