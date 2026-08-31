# Shared test fixture authority

`tests_support.py` is ROLE06-owned global test infrastructure. It must track pushed producer contracts without retaining compatibility aliases for superseded identities.

`frozen_runtime_manifest()` carries the canonical project-manifest digest required by the pushed RunLaunchManifest contract. Producer-specific launch identity remains owned by Experimentation; the fixture only supplies deterministic test values.

Future Trial/research-semantics changes are staged only after their producer SHA is pushed. Diagnostic overlays may prove compatibility in advance, but they are not release authority and must not be committed as if an unpublished producer contract were canonical.
