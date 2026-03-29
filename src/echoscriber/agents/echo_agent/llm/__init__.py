"""LLM backend abstraction and factory."""

from __future__ import annotations

from ....agent_api import LLMBackend


def create_backend(
    provider: str,
    model: str,
    api_key: str | None = None,
    base_url: str | None = None,
) -> LLMBackend:
    """Instantiate an LLM backend by provider name."""
    if provider == "anthropic":
        from .anthropic import AnthropicBackend

        return AnthropicBackend(model=model, api_key=api_key)
    if provider == "openai":
        from .openai_backend import OpenAIBackend

        return OpenAIBackend(model=model, api_key=api_key, base_url=base_url)
    if provider == "ollama":
        from .ollama import OllamaBackend

        return OllamaBackend(model=model, base_url=base_url)
    raise ValueError(f"Unknown LLM provider: {provider!r}")
