"""Public orchestration contracts for reusable multi-agent coordination.

The package exposes only explicit coordinator wiring; it never creates a
registry, runtime, provider, or process during import.
"""

from . import multi_agent

__all__ = ["multi_agent"]
