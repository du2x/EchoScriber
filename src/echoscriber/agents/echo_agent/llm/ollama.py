"""Ollama LLM backend via HTTP API."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator


class OllamaBackend:
    def __init__(
        self, model: str = "llama3.1", base_url: str | None = None
    ) -> None:
        self._model = model
        self._base_url = (base_url or "http://localhost:11434").rstrip("/")

    def _build_messages(self, system: str, messages: list[dict]) -> list[dict]:
        return [{"role": "system", "content": system}, *messages]

    async def complete(self, system: str, messages: list[dict]) -> str:
        import httpx

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._base_url}/api/chat",
                json={
                    "model": self._model,
                    "messages": self._build_messages(system, messages),
                    "stream": False,
                },
                timeout=120.0,
            )
            resp.raise_for_status()
            return resp.json()["message"]["content"]

    async def stream(self, system: str, messages: list[dict]) -> AsyncIterator[str]:
        import httpx

        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                f"{self._base_url}/api/chat",
                json={
                    "model": self._model,
                    "messages": self._build_messages(system, messages),
                    "stream": True,
                },
                timeout=120.0,
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    data = json.loads(line)
                    content = data.get("message", {}).get("content", "")
                    if content:
                        yield content
