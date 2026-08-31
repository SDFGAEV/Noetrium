# ROLE02 PSC08 preflight and durability convergence — 2026-08-31

Authority: Playbook §41.20 and `CSR-ROLE00-ROLE02-PSC08-PREFLIGHT-DURABILITY-PROOF-20260831`.

## Authority disposition

Runtime lifecycle, Resource allocation/lease, and Reliability effect/recovery remain distinct durable truths with independent legal states and writers. ROLE02 will not introduce a generic lifecycle state machine, transition manager, or project-specific durable preflight store.

The existing Platform durability kernel is the shared mechanism. Resource workspace metadata and Reliability recovery leases both consume the exact `platform.kernel.durability.durable_file.atomic_replace_bytes` primitive while retaining different checksummed schemas, readers, writers and recovery semantics. `tests/test_durable_resource_temporal_integrity_v1.py` asserts this identity and exercises both authorities end-to-end.

## Preflight composition

The required compiler/doctor/plan/status contribution is read-only. It may project existing Runtime readiness, Resource requirements/leases and Recovery status, but must not allocate, launch, reconcile, renew, release, or write durable state.

The common blocker/severity/remediation envelope is not owned by ROLE02. PSC-03 assigns that neutral diagnostic metadata to ROLE01. ROLE02 therefore filed `state/artifacts/worker-02/CSR-ROLE02-ROLE01-PSC08-PREFLIGHT-UPSTREAM-20260831.md` instead of creating a duplicate diagnostic contract.

The intended composer lives on the Runtime composition surface and consumes Resource public contracts. ROLE01 must first publish PSC-03 and declare the reviewed top-level `runtime -> resource` dependency in the canonical catalog. Resource and Reliability remain independent authorities after composition.

## Validation

The cross-authority proof is OS-neutral and must pass on Windows and Server2/Linux. Algorithm lower-bound proof is separate and does not weaken forensic completeness, evidence integrity or durability semantics.

Until the ROLE01 producer companion is exact, ROLE02 PSC08 status is `BLOCKED_EXTERNAL`, not `READY_FOR_REVIEW`; no placeholder or weak Mapping/object contract is permitted.