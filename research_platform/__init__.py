"""Noetrium's producer-owned Research OS infrastructure.

The discoverable convenience entrypoint is noetrium. This package exports
only Platform contracts and composition facades; reusable method components
live in the sibling components package and depend inward on this layer.
"""

from research_platform.experimentation.api import (
    CompiledResearchPlan,
    ExperimentRunner,
    ExperimentRunnerPort,
    ResearchMethodHost,
    ResearchMethodHostPort,
    ResearchPlanDiff,
    compile_research_plan,
    diff_research_plans,
    resolve_research_requirements,
)

__all__ = [
    "CompiledResearchPlan",
    "ExperimentRunner",
    "ExperimentRunnerPort",
    "ResearchMethodHost",
    "ResearchMethodHostPort",
    "ResearchPlanDiff",
    "compile_research_plan",
    "diff_research_plans",
    "resolve_research_requirements",
]
