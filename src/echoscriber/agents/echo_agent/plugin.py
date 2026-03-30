"""EchoAgent — default AgentPlugin implementation."""

from __future__ import annotations

import asyncio
import logging
import threading

from PySide6.QtCore import QObject, QThread, Signal

from ...agent_api import LLMBackend, TranscriptFeed
from ...models import AgentMode, AgentResult
from .context import ContextBuilder
from .llm import create_backend
from .prompts import PROMPTS

logger = logging.getLogger(__name__)

_PERSUASION_MODES = (AgentMode.PERSUADE, AgentMode.DEBRIEF)


class _AgentWorker(QThread):
    """Runs the LLM call off the GUI thread with proper Qt thread affinity."""

    token_received = Signal(str)
    completed = Signal(AgentResult)
    error = Signal(str)

    def __init__(
        self,
        llm: LLMBackend,
        ctx: ContextBuilder,
        mode: AgentMode,
        query: str | None,
        cancel_event: threading.Event,
        goal: str | None = None,
    ) -> None:
        super().__init__()
        self._llm = llm
        self._ctx = ctx
        self._mode = mode
        self._query = query
        self._cancel = cancel_event
        self._goal = goal

    def run(self) -> None:
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self._run_async())
            finally:
                loop.close()
        except Exception as exc:
            logger.exception("Agent worker error")
            self.error.emit(str(exc))

    async def _run_async(self) -> None:
        if self._mode in (AgentMode.DECISIONS, AgentMode.ACTIONS, AgentMode.DEBRIEF):
            await self._ctx.ensure_summaries(self._llm)

        context = self._ctx.build(self._mode, self._query)
        system_prompt = PROMPTS[self._mode]

        user_content = ""
        if self._goal:
            user_content += f"<goal>\n{self._goal}\n</goal>\n\n"
        user_content += f"<transcript>\n{context}\n</transcript>"
        if self._query:
            user_content += f"\n\nUser question: {self._query}"

        messages = [{"role": "user", "content": user_content}]

        full_response: list[str] = []
        async for token in self._llm.stream(system_prompt, messages):
            if self._cancel.is_set():
                return
            full_response.append(token)
            self.token_received.emit(token)

        result = AgentResult(
            mode=self._mode,
            query=self._query,
            response="".join(full_response),
        )
        self.completed.emit(result)


class EchoAgent(QObject):
    """Default agent plugin. Uses an LLM to answer questions about the transcript."""

    token_received = Signal(str)
    completed = Signal(AgentResult)
    error = Signal(str)

    name: str = "EchoAgent"
    modes: list[AgentMode] = list(AgentMode)

    def __init__(self) -> None:
        super().__init__()
        self._feed: TranscriptFeed | None = None
        self._llm: LLMBackend | None = None
        self._persuasion_llm: LLMBackend | None = None
        self._persuasion_goal: str = ""
        self._token_budget: int = 8000
        self._cancel_event = threading.Event()
        self._worker: _AgentWorker | None = None

    def configure(
        self,
        provider: str = "anthropic",
        model: str = "claude-sonnet-4-20250514",
        api_key: str | None = None,
        base_url: str | None = None,
        token_budget: int = 8000,
    ) -> None:
        self._llm = create_backend(provider, model, api_key, base_url)
        self._token_budget = token_budget

    def configure_persuasion(
        self,
        goal: str = "",
        provider: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        """Configure the persuasion modes with a goal and optional separate LLM."""
        self._persuasion_goal = goal
        if provider and model:
            self._persuasion_llm = create_backend(provider, model, api_key, base_url)

    def attach(self, feed: TranscriptFeed) -> None:
        self._feed = feed

    def run(self, mode: AgentMode, query: str | None = None) -> None:
        if self._feed is None or self._llm is None:
            self.error.emit("Agent not configured. Set LLM provider in settings.")
            return

        if mode in _PERSUASION_MODES and not self._persuasion_goal:
            self.error.emit("No persuasion goal set. Add a goal to the 'persuasion' section in settings.")
            return

        # Cancel any in-flight worker
        if self._worker is not None and self._worker.isRunning():
            self._cancel_event.set()
            self._worker.wait(5000)

        self._cancel_event.clear()

        # Use persuasion-specific LLM if configured, otherwise fall back to default
        llm = self._llm
        goal: str | None = None
        if mode in _PERSUASION_MODES:
            if self._persuasion_llm is not None:
                llm = self._persuasion_llm
            goal = self._persuasion_goal

        ctx = ContextBuilder(self._feed, self._token_budget)
        self._worker = _AgentWorker(llm, ctx, mode, query, self._cancel_event, goal=goal)
        self._worker.token_received.connect(self.token_received)
        self._worker.completed.connect(self.completed)
        self._worker.error.connect(self.error)
        self._worker.start()

    def cancel(self) -> None:
        self._cancel_event.set()
        if self._worker is not None and self._worker.isRunning():
            self._worker.wait(5000)
