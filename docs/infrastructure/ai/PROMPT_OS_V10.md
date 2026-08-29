# Prompt OS — Round 10

Prompting is treated as compiled, qualified runtime configuration rather than a mutable string.

## Compilation pipeline

```text
Stable Role Spec
 + Typed Dynamic Blocks
 + Role Block Policy
 + Output Schema Digest
 + Frozen Model Identity
 + Decoding Settings
 + Prompt Generation Identity
 -> Budget Check
 -> Compiled Prompt
 -> PromptExecutionContract
 -> Transport
```

### No silent prompt degradation

`PromptBudgetPlanner` measures the exact static/dynamic blocks against the configured context and reserved output budget. If it does not fit, it raises `PromptBudgetExceeded` with a full budget report. It never truncates memory, drops tools, shortens output tokens, swaps models, or silently summarizes context.

### Output contracts

Output schemas are centrally registered and content-digested. Request evidence binds both schema ID and schema digest so an edited schema cannot masquerade as the same prompt generation.

Schema JSON is deep-frozen at `OutputSchemaSpec` construction. Prompt-generation payloads and reconstructed/model-visible request bodies use JSON-serializable frozen mappings/arrays: callers retain normal JSON equality/serialization semantics, but neither top-level nor nested values can be mutated after the digest-bound cut is formed. The request-build transaction freezes the body immediately after the body builder returns and the model-request recorder repeats the freeze at its durable authority boundary, so contracts, content-addressed bytes and transport-visible bodies derive from one immutable JSON cut.

### Durable publication

`DurablePromptRegistry` publishes one write-once generation and atomically replaces one `ACTIVE` pointer. The generation binds prompt text, decoding, role block policies and output schema digests. Loading recomputes both the outer generation hash and each bundle hash.

### Qualification

Canary evidence and outcome lineage remain separate from publication. A candidate prompt can be generated and stored without becoming active. Promotion should require exact model/revision + suite + role qualification; no unqualified fallback prompt is activated automatically.

## Role design v5

- Planner: strict authority hierarchy, one executable next action, verifier-only completion, no hidden CoT requirement.
- Semantic: J_mem-grounded derivation, evidence IDs, minimal representation, no private evaluation evidence.
- Meta: neutral AOR only, fixed structural grammar, one intent or NO_EDIT, no activation/tool/model/prompt authority.
- Diagnostic: separates proven cause/correlation/unknowns and repeats only mechanically authorized recovery.
