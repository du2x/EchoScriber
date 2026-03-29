# ADR-001: Agent Plugin Boundary Strategy

**Status:** Accepted
**Date:** 2026-03-29
**Deciders:** @du2x

## Context

EchoScriber has two distinct concerns: (1) realtime audio transcription and (2) agentic intelligence on top of the transcript. These have different dependency profiles (audio/STT vs LLM SDKs), different rates of change, and different audiences — the transcription pipeline is stable infrastructure while the agent layer is the experimentation surface.

We need to decide how to separate these concerns and when (if ever) to split them into independent repositories.

## Decision

**Keep both in a single repository with a protocol-defined boundary.** Defer extraction to a separate repo until the contract is proven stable through real usage.

### The boundary

Two Python protocols in `agent_api.py` define the contract:

- **`TranscriptFeed`** (EchoScriber → Agent): read-only access to the transcript store. Methods: `subscribe()`, `recent()`, `search()`, `all_segments()`, `session_id`.
- **`AgentPlugin`** (Agent → EchoScriber): the interface any agent must satisfy. Attributes: `name`, `modes`. Methods: `attach()`, `run()`, `cancel()`. Qt signals: `token_received`, `completed`, `error`.

EchoScriber owns everything on the left side of the boundary (audio, STT, store, GUI pane). Agent implementations own everything on the right (context building, LLM calls, prompts, retrieval strategy).

### Plugin loading

Dynamic import via `importlib.import_module()`. The settings key `agent_plugin` points to a Python module that exposes `create_plugin() -> AgentPlugin`. Default: `echoscriber.agents.echo_agent`.

### Dependency isolation

Agent dependencies are optional: `pip install echoscriber[agent]`. The app runs without any agent (transcription-only mode). The GUI gracefully disables agent controls when no plugin loads.

## Why not separate repos now

1. **The contract is unproven.** `TranscriptFeed` and `AgentPlugin` were designed from first principles but have not been exercised against real multi-hour transcription sessions. Fields will likely be added, method signatures adjusted.

2. **Iteration speed.** Changing a protocol field across two repos requires coordinated releases and version pinning. In a single repo it's a one-line edit.

3. **The GUI integration is tight.** The agent pane, mode dropdown, hotkeys, and streaming card renderer live in EchoScriber's GUI layer. A separate agent repo would either need to ship Qt widgets (coupling it to the GUI framework) or leave all rendering in EchoScriber (duplicating the concern).

4. **No external consumer yet.** Extraction is justified when a second consumer needs the contract as a standalone package. Until then, it's premature packaging overhead.

## When to extract

Revisit this decision when **any two** of the following are true:

- [ ] The `agent_api.py` protocols have been stable (no breaking changes) for 3+ iterations of real usage.
- [ ] A second agent implementation exists outside the `agents/` directory (separate author, separate repo desired).
- [ ] The agent dependency footprint (`anthropic`, `openai`, `httpx`) causes installation problems for transcription-only users despite being optional.
- [ ] Someone wants to use the agent plugin contract with a non-EchoScriber transcript source.

### Extraction plan (when the time comes)

1. Publish `echoscriber-agent-api` as a tiny standalone package containing `agent_api.py` and `models.py` (shared types only).
2. Both EchoScriber and any external agent depend on `echoscriber-agent-api`.
3. Move `agents/echo_agent/` to its own repo, depending on `echoscriber-agent-api`.
4. EchoScriber keeps `transcript_store.py` and `agent_pane.py` — these are platform, not plugin.

Estimated effort: ~30 minutes of `git filter-repo` + packaging.

## Consequences

**Positive:**
- Fast iteration on both transcription and agent code.
- Single CI pipeline, single branch, shared types with no version drift.
- Contributors can fork once and experiment with agents immediately.

**Negative:**
- Agent code ships in the same package even when unused (mitigated by optional deps).
- No enforced boundary at the package level — discipline is required to keep agent code from importing EchoScriber internals beyond the protocol.

**Risks:**
- If the boundary is violated (agent code reaches into `session.py`, `capture.py`, etc.), extraction becomes harder. Mitigated by: protocols are the only import path; code review should flag violations.

## References

- `src/echoscriber/agent_api.py` — protocol definitions
- `src/echoscriber/agents/echo_agent/` — reference implementation
- `README.md` — "Build Your Own Agent" guide
