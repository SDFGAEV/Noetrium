# Noetrium examples

The examples in this directory are small, deterministic entry points into public Noetrium contracts. They intentionally avoid private test helpers, hidden state, API keys, and machine-specific infrastructure.

## Quickstart: compile a reproducible experiment plan

Run:

```bash
python examples/quickstart_experiment_plan.py
```

The example freezes two study variants into a `StudyProtocol`, binds each variant to an explicit provider identity, compiles an `ExperimentPlan`, and verifies that its protocol, binding, and plan digests remain consistent.

Expected shape:

```text
study=noetrium-quickstart
variants=control,treatment
repetitions=3
protocol_digest=<sha256>
plan_digest=<sha256>
plan_consistent=true
```
