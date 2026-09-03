# Noetrium Agent Method Coverage Audit

Date: 2026-09-03
Scope: current master after the Noetrium aggregation work, including research lifecycle, model/agent/environment contracts, evidence, experimentation, and the research workbench.

## Executive conclusion

Noetrium can host the core implementation of a broad class of Agent papers through injected Method, Model, Environment, Participant, Workload, and Study components. The platform does not need to contain every paper algorithm. The downstream method owns its algorithm; Noetrium owns lifecycle, capability binding, isolation, checkpoint identity, evidence, evaluation, and publication.

Before this audit, the platform was not sufficient for a complete paper workflow because numerical data preparation and publication were only contracts. The new research.workbench aggregate closes the common infrastructure gap with:

- immutable schema-bound DataTable values;
- source and transformation lineage digests;
- deterministic filtering, projection, derived columns, and train/test splits;
- shared numeric summaries and two-group effect comparisons;
- CSV and JSONL readers;
- CSV, Markdown, and LaTeX table output;
- deterministic SVG line, bar, and scatter output.

The workbench is standard-library-first. Pandas, NumPy, SciPy, Matplotlib, PyTorch, vector databases, and simulator SDKs remain downstream or provider adapters. This keeps the public method surface decoupled from vendor details.

## Coverage matrix

| Method family | Platform seam | Verdict | Boundary |
|---|---|---|---|
| ReAct, tool-use, function calling | Agent loop, capability operation, effect journal, recovery | Strong | Downstream supplies tool policy and tool provider |
| RAG and evidence-grounded agents | Evidence query, source snapshots, artifact references, model capability | Strong with adapter | Vector/full-text index and embedding model are provider concerns |
| Memory, skill learning, reflection | Memory/skill ports, checkpoint envelope, participant runtime identity | Strong | Downstream defines memory semantics and storage adapter |
| Planning, ToT, GoT, MCTS, search | Whole-method host and stateful method program | Strong | Search algorithm is downstream code; checkpoint state is injected |
| Single-agent RL and PPO | Environment, MethodProgram, Study matrix, checkpoints, measurements | Method-host ready | Tensor trainer, replay buffer, GPU loop, and RL library are not platform core |
| MARL and multi-agent coordination | Participant topology, orchestration transport, shared study/workload seams | Method-host ready | Domain simulator and communication/game algorithm are downstream |
| Embodied, web, GUI, browser agents | Environment action/observation contracts and capability effects | Provider-ready | Browser/game/robot backend must be supplied |
| World models and model-based planning | Model capability, stateful method, artifact/checkpoint identity | Method-host ready | Tensor storage/training backend is downstream |
| Multi-modal/VLM agents | Typed model capability families and environment artifacts | Provider-ready | Image/video/audio preprocessing backend is downstream |
| Long-horizon autonomous agents | Run control, evidence validity, recovery and durable artifacts | Strong | Domain task decomposition remains downstream |
| Benchmarking and ablations | Variant bindings, deterministic assignments, study matrix, workload graph | Strong | Paper-specific factor definitions are downstream |
| Data processing and feature preparation | research.workbench.DataTable and TablePipeline | Now usable | Parquet/database/cloud readers need adapters |
| Statistical evaluation | ScientificStatistics, summaries, effects, missing policy | Common baseline | Advanced tests/power analysis require a scientific-statistics adapter |
| Paper tables and plots | StandardTableRenderer, SvgFigureRenderer, report digest | Now usable | Matplotlib/Plotly styling can be an output adapter |
| Reproducibility and provenance | Dataset versions, measurement cuts, analysis identity, artifacts | Strong | Physical storage and external dependency lockfiles stay outside core |

## What implementable downstream means

A paper is implementable downstream when its novel method can be written as a typed MethodProgram or a composed Agent/Model/Environment component, while the platform supplies:

1. a frozen project and method binding;
2. a deterministic workload/study matrix;
3. an environment and model capability adapter;
4. run-local checkpoints and evidence artifacts;
5. structured measurements;
6. a single analysis and publication path.

This is deliberately different from putting a generic run() function into every paper project. The method may remain completely paper-specific, but the experiment mechanics are shared.

## Remaining platform-level limits

The audit does not claim that the core package itself is a full ML framework. The following are intentionally provider or downstream responsibilities:

- GPU/distributed execution and accelerator-specific tensor storage;
- Transformer, diffusion, VLM, simulator, browser, robotics, and vector-index implementations;
- domain-specific replay buffers, neural optimizers, schedulers, and loss functions;
- advanced inference such as mixed-effects models, permutation/bootstrap families, multiple-comparison correction, power analysis, and inter-rater reliability;
- high-volume Parquet/Arrow/database ingestion;
- publication-specific journal templates and typography.

These are extension points, not reasons to duplicate lifecycle, lineage, metrics, or plotting code in each paper.

## Architectural decisions retained

- Existing Dataset, Measurement, Study, Analysis identity, and Artifact authorities remain authoritative.
- research.workbench is an aggregation layer over those authorities, not a replacement experiment system.
- Physical file locations are never part of table, analysis, or figure identity.
- Every transformation that changes research data requires an explicit operation and configuration digest.
- Numeric output uses finite-value validation and explicit missing-value policy.
- Figure and table formats are output concerns; downstream methods do not import plotting libraries.
- Public downstream authors may import the stable noetrium.contracts.research surface without learning internal package paths.

## Audit conclusion

The architecture is sufficient for the core method of most Agent-paper families, provided the method-specific backend is injected. It was not sufficient for the surrounding scientific workflow until the research workbench was added. The main follow-up is to add optional scientific backend adapters and richer statistical procedures without moving those vendor-specific details into the public contracts.
