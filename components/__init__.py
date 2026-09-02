"""Reusable Noetrium research components.

Layer 1 (agent, memory, tools) provides reusable single-agent building blocks.
Layer 2 (multi_agent) coordinates those agents through explicit topologies.
This package depends on research_platform; research_platform never imports it.
"""

from .agent import *
from .memory import *
from .tools import *
from .bridges import *
from .multi_agent import *

