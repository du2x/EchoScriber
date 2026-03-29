"""Plugin contract between EchoScriber and any agent implementation.

EchoScriber owns TranscriptFeed (data in) and the GUI pane.
Any agent plugin implements AgentPlugin (results out).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

from .models import AgentMode, AgentResult, TranscriptSegment


class TranscriptFeed(Protocol):
    """Read-only interface that EchoScriber provides to agent plugins."""

    def subscribe(self, callback: Callable[[TranscriptSegment], None]) -> None:
        """Register a callback invoked on every final segment."""
        ...

    def recent(self, n_minutes: float) -> list[TranscriptSegment]:
        """Return final segments from the last *n_minutes*."""
        ...

    def search(self, query: str, limit: int = 20) -> list[TranscriptSegment]:
        """Full-text search across the current session."""
        ...

    def all_segments(self) -> list[TranscriptSegment]:
        """Return every final segment in the current session."""
        ...

    @property
    def session_id(self) -> str: ...


@runtime_checkable
class AgentPlugin(Protocol):
    """Interface that every agent implementation must satisfy."""

    name: str
    modes: list[AgentMode]

    def attach(self, feed: TranscriptFeed) -> None:
        """Bind the plugin to a transcript feed. Called once at startup."""
        ...

    def run(self, mode: AgentMode, query: str | None = None) -> None:
        """Trigger a completion. Results arrive via the signals below."""
        ...

    def cancel(self) -> None:
        """Cancel an in-flight completion if possible."""
        ...


class LLMBackend(Protocol):
    """Provider-agnostic LLM interface used by agent implementations."""

    async def complete(self, system: str, messages: list[dict]) -> str: ...

    async def stream(
        self, system: str, messages: list[dict]
    ) -> AsyncIterator[str]: ...
