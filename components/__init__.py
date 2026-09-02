"""Canonical reusable component layer for downstream agent research.

The component layer depends on public Noetrium contracts and platform ports;
it does not own platform authority or application-specific experiments.
"""

from . import reference

__all__ = ["reference"]
