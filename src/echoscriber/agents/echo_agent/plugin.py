"""EchoAgent — default AgentPlugin implementation."""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal

from ...agent_api import LLMBackend, TranscriptFeed
from ...models import AgentMode, AgentResult
from .context import ContextBuilder
from .llm import create_backend
from .prompts import PROMPTS

if TYPE_CHECKING:
    from ...transcript_store import TranscriptStore

logger = logging.getLogger(__name__)


class EchoAgent(QObject):
    """Default agent plugin. Uses an LLM to answer questions about the transcript."""

    token_received = Signal(str)
    completed = Signal(AgentResult)
    error = Signal(str)

    name: str = "EchoAgent"
    modes: list[AgentMode] = list(AgentMode)

    def __init__(self) -> None:
        super().__init__()
        self._feed: TranscriptStore | None = None
        self._ctx: ContextBuilder | None = None
        self._llm: LLMBackend | None = None
        self._cancel_event = threading.Event()
        self._worker_thread: threading.Thread | None = None

    def configure(
        self,
        provider: str = "anthropic",
        model: str = "claude-sonnet-4-20250514",
        api_key: str | None = None,
        base_url: str | None = None,
        token_budget: int = 8000,
    ) -> None:
        self._llm = create_backend(provider, model, api_key, base_url)
        if self._feed is not None:
            self._ctx = ContextBuilder(self._feed, token_budget)
        self._token_budget = token_budget

    def attach(self, feed: TranscriptFeed) -> None:
        self._feed = feed  # type: ignore[assignment]
        if self._llm is not None:
            self._ctx = ContextBuilder(self._feed, getattr(self, "_token_budget", 8000))

    def run(self, mode: AgentMode, query: str | None = None) -> None:
        if self._ctx is None or self._llm is None:
            self.error.emit("Agent not configured. Set LLM provider in settings.")
            return

        self._cancel_event.clear()

        self._worker_thread = threading.Thread(
            target=self._run_sync, args=(mode, query), daemon=True
        )
        self._worker_thread.start()

    def cancel(self) -> None:
        self._cancel_event.set()

    def _run_sync(self, mode: AgentMode, query: str | None) -> None:
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self._run_async(mode, query))
            finally:
                loop.close()
        except Exception as exc:
            logger.exception("Agent error")
            self.error.emit(str(exc))

    async def _run_async(self, mode: AgentMode, query: str | None) -> None:
        context = self._ctx.build(mode, query)
        system_prompt = PROMPTS[mode]

        user_content = f"<transcript>\n{context}\n</transcript>"
        if query:
            user_content += f"\n\nUser question: {query}"

        messages = [{"role": "user", "content": user_content}]

        full_response: list[str] = []
        async for token in self._llm.stream(system_prompt, messages):
            if self._cancel_event.is_set():
                return
            full_response.append(token)
            self.token_received.emit(token)

        result = AgentResult(
            mode=mode,
            query=query,
            response="".join(full_response),
        )
        self.completed.emit(result)
