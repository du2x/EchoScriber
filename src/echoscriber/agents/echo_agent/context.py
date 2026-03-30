"""ContextBuilder — assembles the right transcript context per AgentMode."""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import TYPE_CHECKING

from ...models import AgentMode, TranscriptSegment
from ...transcript_store import TranscriptStore
from .prompts import CHUNK_SUMMARY_PROMPT

if TYPE_CHECKING:
    from ...agent_api import LLMBackend

logger = logging.getLogger(__name__)

_CHUNK_MINUTES = 10.0
_LIVE_WINDOW_SECONDS = 300  # don't summarize the last 5 minutes


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
        if mode == AgentMode.PERSUADE:
            return self._for_persuade()
        if mode == AgentMode.DEBRIEF:
            return self._for_full_session()
        return self._for_summary()

    async def ensure_summaries(self, llm: LLMBackend) -> None:
        """Lazily generate chunk summaries for unsummarized portions of the session."""
        latest_end = self._store.latest_summary_end()
        start = latest_end if latest_end is not None else 0.0
        cutoff = time.time() - _LIVE_WINDOW_SECONDS

        if start >= cutoff:
            return  # nothing to summarize

        rows = self._store.segments_in_range(start, cutoff)
        if len(rows) < 5:
            return  # not enough material to summarize

        # Group into chunks of ~10 minutes
        chunks: list[list[tuple[int, TranscriptSegment]]] = []
        current_chunk: list[tuple[int, TranscriptSegment]] = []
        chunk_start_ts = rows[0][1].timestamp

        for row in rows:
            seg_id, seg = row
            if seg.timestamp - chunk_start_ts >= _CHUNK_MINUTES * 60 and current_chunk:
                chunks.append(current_chunk)
                current_chunk = []
                chunk_start_ts = seg.timestamp
            current_chunk.append(row)

        if current_chunk:
            chunks.append(current_chunk)

        for chunk in chunks:
            segment_ids = [row[0] for row in chunk]
            segments = [row[1] for row in chunk]
            chunk_text = _format_segments(segments)

            if _estimate_tokens(chunk_text) < 20:
                continue  # too short to be worth summarizing

            try:
                summary = await llm.complete(
                    CHUNK_SUMMARY_PROMPT,
                    [{"role": "user", "content": chunk_text}],
                )
                self._store.save_chunk_summary(
                    chunk_start=segments[0].timestamp,
                    chunk_end=segments[-1].timestamp,
                    segment_ids=segment_ids,
                    summary=summary,
                    model_used="agent",
                )
                logger.info(
                    "Cached chunk summary: %s–%s (%d segments)",
                    datetime.fromtimestamp(segments[0].timestamp).strftime("%H:%M"),
                    datetime.fromtimestamp(segments[-1].timestamp).strftime("%H:%M"),
                    len(segments),
                )
            except Exception:
                logger.exception("Failed to summarize chunk")

    # -- Context assembly per mode ----------------------------------------

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
            minutes_since = max(0, (time.time() - latest_end) / 60) or 10.0
            recent = self._store.recent(minutes_since)
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

    def _for_persuade(self) -> str:
        segments = self._store.recent(10.0)
        if not segments:
            return "(No transcript yet.)"
        text = _format_segments(segments)
        return _trim_to_budget(text, self._budget)
