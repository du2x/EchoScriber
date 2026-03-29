# EchoScriber

A platform for experimenting with agentic systems that assist during realtime conversations.

EchoScriber captures live audio (microphone and system playback), transcribes it in realtime, and feeds the transcript to a pluggable agent that can answer questions, extract decisions, summarize discussions, and generate other completions on demand.

**The transcription pipeline is ready. The interesting part is what you build on top of it.**

Fork this repo and write your own agent backend. The plugin contract is intentionally minimal — implement a few methods, point to your module in settings, and your agent is live.

## Architecture

```
Audio capture → STT engine → Transcript store → [Your agent here] → GUI
```

**Audio layer** — PipeWire/PulseAudio mic and system loopback capture with optional echo cancellation.

**STT layer** — Swappable backends: faster-whisper (GPU-accelerated) and HuggingFace transformers. Supports Portuguese (BR) and English.

**Transcript store** — SQLite with FTS5 full-text search. Stores segments with timestamps, supports recent-window queries, keyword search, and cached chunk summaries.

**Agent plugin system** — A stable contract (`TranscriptFeed` + `AgentPlugin` protocols) that any agent implementation can plug into. The default plugin (EchoAgent) is a reference implementation — it's meant to be replaced.

## Build Your Own Agent

The whole point of this project is to make it easy to experiment with different agentic approaches on a live transcript stream. Here's how.

### The contract

Your agent receives a `TranscriptFeed` — a read-only interface to the transcript store:

```python
class TranscriptFeed(Protocol):
    def subscribe(self, callback: Callable[[TranscriptSegment], None]) -> None: ...
    def recent(self, n_minutes: float) -> list[TranscriptSegment]: ...
    def search(self, query: str, limit: int = 20) -> list[TranscriptSegment]: ...
    def all_segments(self) -> list[TranscriptSegment]: ...
    def session_id(self) -> str: ...
```

Your agent exposes results back to the GUI via Qt signals:

```python
class AgentPlugin(Protocol):
    name: str
    modes: list[AgentMode]  # which modes your agent supports

    def attach(self, feed: TranscriptFeed) -> None: ...
    def run(self, mode: AgentMode, query: str | None = None) -> None: ...
    def cancel(self) -> None: ...

    # Qt signals your class must define:
    # token_received = Signal(str)      — streaming tokens
    # completed = Signal(AgentResult)   — final result
    # error = Signal(str)               — failure
```

That's it. Everything else — how you build context, which LLM you call, whether you use RAG or chain-of-thought or a local model or no model at all — is up to you.

### Step-by-step: write a minimal agent

1. **Fork and clone** this repo.

2. **Create your agent module** anywhere under `src/echoscriber/agents/`:

```
src/echoscriber/agents/my_agent/
├── __init__.py
└── plugin.py
```

3. **Implement the plugin** in `plugin.py`:

```python
from PySide6.QtCore import QObject, Signal
from echoscriber.agent_api import TranscriptFeed
from echoscriber.models import AgentMode, AgentResult

class MyAgent(QObject):
    token_received = Signal(str)
    completed = Signal(AgentResult)
    error = Signal(str)

    name = "MyAgent"
    modes = [AgentMode.SUMMARY, AgentMode.QA]  # pick the modes you support

    def attach(self, feed: TranscriptFeed) -> None:
        self._feed = feed

    def run(self, mode: AgentMode, query: str | None = None) -> None:
        # Read from the feed
        segments = self._feed.recent(10.0)
        transcript = "\n".join(s.text for s in segments)

        # Do your thing — call an LLM, run a local model, use a RAG pipeline...
        response = your_logic_here(transcript, mode, query)

        # Emit result
        self.completed.emit(AgentResult(
            mode=mode, query=query, response=response
        ))

    def cancel(self) -> None:
        pass
```

4. **Export the factory** in `__init__.py`:

```python
from .plugin import MyAgent

def create_plugin():
    return MyAgent()
```

5. **Point to your agent** in `~/.config/echoscriber/settings.json`:

```json
{
  "agent_plugin": "echoscriber.agents.my_agent"
}
```

6. **Run it**: `echoscriber` — your agent is now live, responding to the Ask Agent button and hotkeys.

### Ideas to try

- **RAG pipeline** — embed transcript chunks with a local model, retrieve by similarity on each query
- **Multi-agent orchestration** — one agent extracts entities, another answers questions, a third summarizes
- **Proactive agent** — subscribe to the feed and push notifications when it detects action items or decisions, without waiting for the user to ask
- **Local-only agent** — use Ollama or llama.cpp, never send transcript data to the cloud
- **Structured extraction** — output JSON with decisions, owners, deadlines, sentiment
- **Cross-session memory** — persist context across sessions, build a knowledge base from past conversations
- **Tool-using agent** — give the LLM tools to search the web, look up docs, or run code based on what's being discussed
- **Fine-tuned specialist** — train a small model on your meeting patterns for faster, cheaper completions

### Streaming

For a responsive UX, emit `token_received` as tokens arrive from your LLM rather than waiting for the full response. The agent pane renders tokens incrementally. See `agents/echo_agent/plugin.py` for an example using async streaming.

## Default Agent (EchoAgent)

The included EchoAgent is a reference implementation with:

- Provider-agnostic LLM layer (Anthropic, OpenAI, Ollama)
- Adaptive context building per mode (recent window, full session scan, FTS5 search)
- Token-budgeted context assembly
- Streaming output

### Modes

| Mode | Input | Output |
|------|-------|--------|
| Summary | none | Condensed summary of recent transcript |
| Key Decisions | none | Extracted decisions and conclusions |
| Action Items | none | Checklist of todos and commitments |
| Q&A | user question | Answer grounded in transcript context |
| Explain | user question | Clarification of something from the conversation |

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

# Full install (recommended)
pip install -e ".[agent,faster-whisper]"
```

**Important:** Always run `echoscriber` from the virtualenv where you installed the extras. If you install with just `pip install -e .` (or into a global Python), `torch` and `faster-whisper` won't be available and the STT engine will silently fall back to CPU — or fail to load entirely.

### System dependencies

```bash
sudo apt install pulseaudio-utils   # provides parec for audio capture
```

### GPU acceleration

GPU inference requires an NVIDIA GPU with CUDA support. The STT engine auto-detects CUDA via `torch.cuda.is_available()` and uses it when present.

To verify GPU is working:

```bash
# Check CUDA is visible to Python
python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"

# Check faster-whisper loads on GPU
python -c "from faster_whisper import WhisperModel; WhisperModel('tiny', device='cuda', compute_type='float16'); print('GPU OK')"

# Monitor GPU usage while EchoScriber is running
watch -n 1 nvidia-smi
```

If `torch.cuda.is_available()` returns `False`, the STT engine falls back to CPU silently. Common causes:
- `torch` not installed (install with `pip install -e ".[faster-whisper]"`)
- Running `echoscriber` outside the virtualenv where torch was installed
- NVIDIA drivers or CUDA toolkit not installed on the system
- PyTorch installed without CUDA support (CPU-only wheel)

### Configuration

Settings are stored in `~/.config/echoscriber/settings.json`:

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

## Contributing

The best way to contribute is to build a novel agent and share what you learn. If you build something interesting, open a PR or an issue describing your approach.

## License

MIT
