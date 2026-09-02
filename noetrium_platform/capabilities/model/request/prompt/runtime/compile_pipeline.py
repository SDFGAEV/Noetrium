from __future__ import annotations

from dataclasses import dataclass

from .blocks import PromptBlock, PromptBlockPolicy
from .budget import PromptBudgetPlanner, PromptBudgetReport
from .compiler import CompiledPrompt, PromptCompiler
from .runtime_contracts import PromptResolution
from .schema import OutputSchemaRegistry, OutputSchemaSpec


@dataclass(frozen=True, slots=True)
class PromptCompilationReceipt:
    generation_id: str
    prompt_id: str
    bundle_digest: str
    schema_id: str
    schema_digest: str
    compiled: CompiledPrompt
    budget: PromptBudgetReport


class PromptCompilePipeline:
    """Strict no-degradation Prompt compilation transaction."""

    def __init__(
        self,
        *,
        compiler: PromptCompiler | None = None,
        budget_planner: PromptBudgetPlanner | None = None,
    ) -> None:
        self.compiler = compiler or PromptCompiler()
        self.budget_planner = budget_planner or PromptBudgetPlanner()

    def compile(
        self,
        *,
        resolution: PromptResolution,
        policy: PromptBlockPolicy,
        blocks: tuple[PromptBlock, ...],
        schemas: OutputSchemaRegistry,
        context_length: int,
    ) -> PromptCompilationReceipt:
        bundle = resolution.bundle
        schema = schemas.require(bundle.output_schema)
        # Budget check is measurement only. It never truncates/drops blocks or
        # reduces output budget. The exact same block set then enters compile.
        budget = self.budget_planner.check(
            bundle,
            blocks,
            context_length=context_length,
        )
        compiled = self.compiler.compile(bundle, policy, blocks)
        return PromptCompilationReceipt(
            generation_id=resolution.generation_id,
            prompt_id=bundle.prompt_id,
            bundle_digest=bundle.digest,
            schema_id=schema.schema_id,
            schema_digest=schema.digest(),
            compiled=compiled,
            budget=budget,
        )
