from __future__ import annotations

import unittest

from noetrium_platform.capabilities.model.request.prompt.runtime import (
    PromptBlock,
    PromptBlockKind,
    PromptBudgetExceeded,
    PromptCompilePipeline,
    PromptRegistry,
    default_block_policies,
    default_output_schemas,
    default_prompt_specs,
)


class PromptCompilePipelineV75Tests(unittest.TestCase):
    def planner(self):
        registry = PromptRegistry(); registry.publish("g75", default_prompt_specs())
        K = PromptBlockKind
        blocks = (
            PromptBlock(K.TASK, "collect wood", "d1", 1),
            PromptBlock(K.VERIFIED_STATE, "inventory empty", "d2", 2),
            PromptBlock(K.TOOL_CATALOG, "mine/craft", "d3", 3),
        )
        return registry.resolve("planner.v6"), blocks

    def test_pipeline_binds_generation_budget_render_and_schema(self):
        resolution, blocks = self.planner()
        receipt = PromptCompilePipeline().compile(
            resolution=resolution,
            policy=default_block_policies()["planner"],
            blocks=blocks,
            schemas=default_output_schemas(),
            context_length=262144,
        )
        self.assertEqual(receipt.generation_id, "g75")
        self.assertEqual(receipt.prompt_id, "planner.v6")
        self.assertEqual(receipt.compiled.block_kinds, ("task","verified_state","tool_catalog"))
        self.assertTrue(receipt.budget.fits)
        self.assertEqual(len(receipt.schema_digest), 64)

    def test_budget_overflow_fails_without_block_dropping_or_output_reduction(self):
        resolution, blocks = self.planner()
        original = tuple((b.kind, b.content, b.source_digest, b.sequence) for b in blocks)
        with self.assertRaises(PromptBudgetExceeded):
            PromptCompilePipeline().compile(
                resolution=resolution,
                policy=default_block_policies()["planner"],
                blocks=blocks,
                schemas=default_output_schemas(),
                context_length=100,
            )
        self.assertEqual(
            tuple((b.kind, b.content, b.source_digest, b.sequence) for b in blocks),
            original,
        )
        self.assertEqual(resolution.bundle.max_output_tokens, 8192)

    def test_forbidden_block_fails_in_validation_instead_of_being_ignored(self):
        resolution, blocks = self.planner(); K = PromptBlockKind
        with self.assertRaises(ValueError):
            PromptCompilePipeline().compile(
                resolution=resolution,
                policy=default_block_policies()["planner"],
                blocks=blocks + (PromptBlock(K.FAILURE_EVIDENCE,"x","bad",4),),
                schemas=default_output_schemas(),
                context_length=262144,
            )


if __name__ == "__main__": unittest.main()
