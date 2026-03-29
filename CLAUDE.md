# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Setup
python -m venv .venv
source .venv/bin/activate
pip install -e ".[agent,faster-whisper]"

# Run the app
echoscriber

# Syntax validation (no test suite yet)
python -m compileall src
```

## Architecture

EchoScriber is a Linux desktop app for experimenting with agentic systems on realtime conversations. Built with **Python 3.10+ and PySide6 (Qt6)**.

### Core modules

- **`app.py`** — Entry point. Creates `QApplication`, instantiates `MainWindow`, runs the Qt event loop.
- **`models.py`** — Data layer: `SourceMode`, `SegmentSource`, `AgentMode` enums, `TranscriptSegment` and `AgentResult` dataclasses, `STTEngine` Protocol.
- **`services.py`** — `SessionConfig` dataclass and legacy `MockRealtimePipeline`.
- **`session.py`** — `SessionController` orchestrates audio capture → AEC → STT → transcript store. Emits Qt signals for partial/final segments, metrics, and errors.
- **`gui.py`** — UI layer with transcript pane, agent pane (65/35 splitter), device/model controls, and agent plugin loader.
- **`config.py`** — Settings persistence in `~/.config/echoscriber/settings.json`.

### Audio subsystem (`audio/`)

- **`devices.py`** — PipeWire/PulseAudio device enumeration via pulsectl.
- **`capture.py`** — Mic and loopback capture workers (QThread-based, using `parec`).
- **`aec.py`** — Echo cancellation via PipeWire module loading.

### STT subsystem (`stt/`)

- **`whisper_adapter.py`** — faster-whisper backend.
- **`hf_adapter.py`** — HuggingFace transformers backend.

### Agent system

- **`agent_api.py`** — Plugin contract: `TranscriptFeed` and `AgentPlugin` protocols. This is the stable boundary.
- **`transcript_store.py`** — SQLite + FTS5 store implementing `TranscriptFeed`. Stores segments, supports full-text search, caches chunk summaries.
- **`agent_pane.py`** — GUI widget: collapsible panel with streaming result cards, mode dropdown, prompt field.
- **`agents/echo_agent/`** — Default `AgentPlugin` implementation:
  - `plugin.py` — `EchoAgent` class wiring context builder → LLM → streaming results.
  - `context.py` — Adaptive context assembly per mode (recent window, full session, FTS5 search).
  - `prompts.py` — System prompts per `AgentMode`.
  - `llm/` — Provider-agnostic backends: Anthropic, OpenAI, Ollama.

### Control flow

1. **Transcription**: Start → `SessionController` → audio workers → STT → `TranscriptSegment` → store + GUI
2. **Agent**: User triggers mode → `AgentPlugin.run()` → `ContextBuilder` reads store → LLM stream → `AgentPane` renders cards

### Plugin contract

Any module exposing `create_plugin() -> AgentPlugin` can replace the default agent. Set `agent_plugin` in settings. See `agent_api.py` for protocols.
