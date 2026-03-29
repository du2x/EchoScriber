# EchoScriber

A platform for experimenting with agentic systems that assist during realtime conversations.

EchoScriber captures live audio (microphone and system playback), transcribes it in realtime, and feeds the transcript to a pluggable agent that can answer questions, extract decisions, summarize discussions, and generate other completions on demand.

## Architecture

```
Audio capture → STT engine → Transcript store → Agent plugin → GUI
```

**Audio layer** — PipeWire/PulseAudio mic and system loopback capture with optional echo cancellation.

**STT layer** — Swappable backends: faster-whisper (GPU-accelerated) and HuggingFace transformers. Supports Portuguese (BR) and English.

**Transcript store** — SQLite with FTS5 full-text search. Stores segments with timestamps, supports recent-window queries, keyword search, and cached chunk summaries.

**Agent plugin system** — A stable contract (`TranscriptFeed` + `AgentPlugin` protocols) that any agent implementation can plug into. The default plugin (EchoAgent) supports multiple LLM providers and five completion modes.

### Agent modes

| Mode | Input | Output |
|------|-------|--------|
| Summary | none | Condensed summary of recent transcript |
| Key Decisions | none | Extracted decisions and conclusions |
| Action Items | none | Checklist of todos and commitments |
| Q&A | user question | Answer grounded in transcript context |
| Explain | user question | Clarification of something from the conversation |

### LLM backends

EchoAgent is provider-agnostic. Supported backends:

- **Anthropic** (Claude)
- **OpenAI** (GPT-4o, etc.)
- **Ollama** (local models)

### Writing a custom agent plugin

Any Python module that exposes `create_plugin() -> AgentPlugin` can replace the default EchoAgent. Set `agent_plugin` in settings to point to your module. See `src/echoscriber/agent_api.py` for the protocol definitions.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate

# Core (transcription only)
pip install -e .

# With agent support
pip install -e ".[agent]"

# With specific STT backend
pip install -e ".[faster-whisper]"
pip install -e ".[agent,faster-whisper]"
```

### System dependencies

```bash
sudo apt install pulseaudio-utils   # provides parec for audio capture
```

### Configuration

Settings are stored in `~/.config/echoscriber/settings.json`. Agent configuration example:

```json
{
  "agent_plugin": "echoscriber.agents.echo_agent",
  "agent": {
    "provider": "anthropic",
    "model": "claude-sonnet-4-20250514",
    "token_budget": 8000
  }
}
```

Set your API key via environment variable (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`) or in the agent config.

## Usage

```bash
echoscriber
```

- Select audio sources, language, and STT model
- Click **Start** to begin transcription
- Use the mode dropdown + **Ask Agent** button (or `Ctrl+Shift+A`) to trigger completions
- `Ctrl+Shift+Q` jumps straight to Q&A mode

## Development

```bash
python -m compileall src   # syntax validation
```

## License

MIT
