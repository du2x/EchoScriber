"""Anthropic (Claude) LLM backend."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator


class AnthropicBackend:
    def __init__(self, model: str = "claude-sonnet-4-20250514", api_key: str | None = None) -> None:
        import anthropic

        self._model = model
        self._client = anthropic.AsyncAnthropic(
            api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"),
        )

    async def complete(self, system: str, messages: list[dict]) -> str:
        resp = await self._client.messages.create(
            model=self._model,
            max_tokens=2048,
            system=system,
            messages=messages,
        )
        return resp.content[0].text

    async def stream(self, system: str, messages: list[dict]) -> AsyncIterator[str]:
        async with self._client.messages.stream(
            model=self._model,
            max_tokens=2048,
            system=system,
            messages=messages,
        ) as stream:
            async for text in stream.text_stream:
                yield text
