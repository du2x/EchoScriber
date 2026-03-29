# EchoScriber

EchoScriber is a Linux-focused realtime speech-to-text desktop prototype based on the PRD.

## Current state

This repository now includes an MVP-aligned project scaffold with:

- PySide6 desktop GUI for source selection, session controls, transcript output, and save/copy actions
- Session configuration model for mic/system/both source modes, AEC toggle, language, and model selection
- Mock realtime pipeline emitting partial/final transcript segments to exercise the UI flow

> Note: audio capture, AEC DSP integration, and real STT backends are represented by placeholders in this initial build.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
echoscriber
```

## Development checks

```bash
python -m compileall src
```
