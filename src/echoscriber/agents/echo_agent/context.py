"""ContextBuilder — assembles the right transcript context per AgentMode."""

from __future__ import annotations

from datetime import datetime

from ...models import AgentMode, TranscriptSegment
from ...transcript_store import TranscriptStore


def _format_segments(segments: list[TranscriptSegment]) -> str:
    lines: list[str] = []
    for seg in segments:
        ts = datetime.fromtimestamp(seg.timestamp).strftime("%H:%M:%S")
        lines.append(f"{ts} [{seg.source.value}] {seg.text}")
    return "\n".join(lines)


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ~1 token per 0.75 words."""
    return int(len(text.split()) / 0.75)


def _trim_to_budget(text: str, budget: int) -> str:
    """Trim text from the beginning to fit within token budget."""
    if _estimate_tokens(text) <= budget:
        return text
    words = text.split()
    target_words = int(budget * 0.75)
    return "... " + " ".join(words[-target_words:])


class ContextBuilder:
    def __init__(self, store: TranscriptStore, token_budget: int = 8000) -> None:
        self._store = store
        self._budget = token_budget

    def build(self, mode: AgentMode, query: str | None = None) -> str:
        if mode == AgentMode.SUMMARY:
            return self._for_summary()
        if mode in (AgentMode.DECISIONS, AgentMode.ACTIONS):
            return self._for_full_session()
        if mode == AgentMode.QA:
            return self._for_qa(query or "")
        if mode == AgentMode.EXPLAIN:
            return self._for_explain(query or "")
        return self._for_summary()

    def _for_summary(self) -> str:
        segments = self._store.recent(15.0)
        if not segments:
            return "(No transcript yet.)"
        text = _format_segments(segments)
        return _trim_to_budget(text, self._budget)

    def _for_full_session(self) -> str:
        cached = self._store.get_cached_summaries()
        if cached:
            summaries = "\n\n".join(
                f"[{datetime.fromtimestamp(c['chunk_start']).strftime('%H:%M')}–"
                f"{datetime.fromtimestamp(c['chunk_end']).strftime('%H:%M')}] "
                f"{c['summary']}"
                for c in cached
            )
            latest_end = cached[-1]["chunk_end"]
            recent = self._store.recent(
                max(0, (self._store._conn.execute("SELECT ?", (latest_end,)).fetchone()[0]
                         - latest_end) / 60) or 10.0
            )
        else:
            summaries = ""
            recent = self._store.all_segments()

        recent_text = _format_segments(recent)
        combined = f"{summaries}\n\n--- Recent ---\n{recent_text}" if summaries else recent_text
        return _trim_to_budget(combined, self._budget)

    def _for_qa(self, query: str) -> str:
        search_results = self._store.search(query, limit=15) if query else []
        recent = self._store.recent(5.0)

        parts: list[str] = []
        if search_results:
            parts.append("--- Relevant excerpts ---")
            parts.append(_format_segments(search_results))
        if recent:
            parts.append("--- Last 5 minutes ---")
            parts.append(_format_segments(recent))
        if not parts:
            return "(No transcript yet.)"

        return _trim_to_budget("\n\n".join(parts), self._budget)

    def _for_explain(self, query: str) -> str:
        recent = self._store.recent(5.0)
        if not recent:
            return "(No transcript yet.)"
        text = _format_segments(recent)
        return _trim_to_budget(text, self._budget)
