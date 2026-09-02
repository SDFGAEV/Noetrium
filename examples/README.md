# Noetrium examples

The examples in this directory are small, deterministic entry points into public Noetrium contracts. They intentionally avoid private test helpers, hidden state, API keys, and machine-specific infrastructure.

## Quickstart: compile a reproducible experiment plan

Run:

```bash
python examples/quickstart_experiment_plan.py
```

The example freezes two study variants into a `StudyProtocol`, binds each variant to an explicit provider identity, compiles an `ExperimentPlan`, and verifies that its protocol, binding, and plan digests remain consistent.

## Quickstart: durable memory

Run `python examples/quickstart_durable_memory.py` to write an episodic memory item to SQLite WAL, close the store, reopen it, and verify the exact content digest.

## Quickstart: foreign framework bridge

Run `python examples/quickstart_langgraph_bridge.py` to normalize a LangGraph-shaped dict state and decision without installing or importing LangGraph.

## Quickstart: interrupt and resume

Run `python examples/quickstart_graph_interrupt.py` to pause a typed state graph at a checkpoint and resume the same thread with an explicit value.

## Quickstart: transport-backed multi-agent

Run `python examples/quickstart_multi_agent_transport.py` to keep the deterministic topology/causal checks while routing node work through an injected transport and membership port.

## Quickstart: reuse a method component

Run `python examples/quickstart_agent_components.py` to execute a public ReAct loop with an explicit Tool Registry. Replace the downstream policy or the whole method without editing Platform source. The reusable component layers and the higher multi-agent tier are documented in [`docs/architecture/COMPONENT_LAYERS.md`](../docs/architecture/COMPONENT_LAYERS.md).

Expected shape:

```text
study=noetrium-quickstart
variants=control,treatment
repetitions=3
protocol_digest=<sha256>
plan_digest=<sha256>
plan_consistent=true
```
