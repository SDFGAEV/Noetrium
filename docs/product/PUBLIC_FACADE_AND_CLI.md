# Public facade and `research` CLI

The common product boundary is intentionally small:

- Python: `research_platform.api`
- CLI: `research`
- lifecycle intents: `run`, `inspect`, `stop`, `resume`, `reconcile`, `evidence`
- existing forensic tools: `research diagnose ...`
- existing management tools: `research manage ...`

`ResearchFacade` owns only product intent translation. It does not own run state, effect certainty, checkpoints, environment truth, model truth, or scientific success. A real application is injected through `ResearchApplicationPort` and must return a typed `ResearchResult` whose action and target match the request.

There is deliberately no ambient service locator and no implicit default production application.

## Python

```python
from research_platform.api import ResearchFacade

facade = ResearchFacade(my_application)
result = facade.inspect("run-123")
```

The request payload is recursively frozen at the facade boundary so callers cannot mutate an in-flight intent after dispatch.

## CLI application binding

Lifecycle commands require an explicit application factory:

```bash
research --application my_project.operator:build_application run run-123
research --application my_project.operator:build_application inspect run-123
research --application my_project.operator:build_application evidence run-123
```

Factories receive the optional `--application-config` path. Downstream projects use that hook to compose their own ROLE 03/04/05 bindings without exposing internal topology to users.

The bundled `research_platform.operator.reference` application exists only to qualify the facade, persistence and installed distribution lifecycle. It is deterministic and checksummed, but it is **not** a substitute for a production run/effect authority and its `reconcile` action does not certify external effect certainty.

## Failure rules

- Missing application bindings fail closed.
- Result action/target drift is rejected.
- Corrupt reference state fails checksum verification.
- Decoded reference state is modeled as immutable typed `ReferenceState` / `ReferenceEvent` values; exact fields and lifecycle transitions are validated before any state is accepted or persisted.
- Real external-effect uncertainty must remain with the owning runtime/reliability authority; the product layer never converts missing evidence into success.

The platform-side generic run-lifecycle handoff required for a default real application is tracked by `CSR-06-GENERIC-RUN-LIFECYCLE-OPERATOR-HANDOFF-20260829`.
