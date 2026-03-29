"""EchoAgent — default AgentPlugin implementation for EchoScriber."""

from .plugin import EchoAgent

__all__ = ["EchoAgent", "create_plugin"]


def create_plugin() -> EchoAgent:
    """Factory function called by EchoScriber's plugin loader."""
    return EchoAgent()
