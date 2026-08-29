# Contributing

Changes must respect the repository's system ownership and public-contract boundaries. Do not fix a foreign authority from a consumer layer; file a cross-system change request when another system must expose or change a capability.

Before proposing a change:

```bash
python scripts/test_system.py check
python scripts/provider_conformance.py check
python scripts/product_assurance_gate.py --full --output product-assurance.json
```

Changes that affect packaging or public surfaces must additionally qualify installed distributions with `scripts/release_distribution.py` from a clean exact Git revision.

Every production change requires focused tests and owning documentation. New top-level test files must match exactly one L0–L8 taxonomy rule. External-effect recovery must remain evidence-driven and fail closed when certainty is unknown.
