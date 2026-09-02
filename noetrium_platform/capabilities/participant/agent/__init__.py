"""Public participant-agent facade.

The runtime implementation remains below ``participant.agent.runtime``; this
facade is the platform-owned cognition entry point for project composition.
"""

from .runtime import AgentCognitionLoop

__all__ = ["AgentCognitionLoop"]
