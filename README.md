# Agent Research Platform

[![Python](https://img.shields.io/badge/Python-%3E%3D3.11-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Version](https://img.shields.io/badge/version-0.43.1-blue)](pyproject.toml)
[![Architecture](https://img.shields.io/badge/architecture-contract--driven-6f42c1)](docs/architecture/PLATFORM_ARCHITECTURE.md)
[![License](https://img.shields.io/badge/license-Apache--2.0-green)](LICENSE)

> **Bilingual documentation / 双语文档:** English and 中文 are maintained together; commands, paths, and code examples are shared to reduce documentation drift.

**English:** A contract-driven platform for building, running, recovering, observing, optimizing, and auditing long-horizon AI-agent systems and research workloads.

**中文：** 一个以契约为核心的平台，用于构建、运行、恢复、观测、优化和审计长时程 AI Agent 系统与科研工作负载。

The platform is intentionally **project-agnostic**: reusable infrastructure stays upstream, while paper-specific scientific semantics stay in downstream projects.

平台刻意保持**项目无关性**：可复用基础设施留在上游平台，论文或具体项目的科学语义留在下游项目。

## Why this platform? / 为什么需要这个平台？

Long-running agent systems fail in more ways than ordinary scripts: processes crash, external effects become uncertain, environments drift, model deployments change, checkpoints become incompatible, and partial logs can be mistaken for valid evidence.

长时间运行的 Agent 系统比普通脚本具有更多失效方式：进程会崩溃，外部副作用可能处于不确定状态，环境会漂移，模型部署会变化，checkpoint 可能失配，残缺日志也可能被错误地当成有效证据。

Agent Research Platform models these concerns as explicit systems with typed contracts, stable ownership, durable identities, evidence-bearing effects, and fail-closed recovery semantics.

Agent Research Platform 将这些问题建模为显式系统，并使用 typed contract、稳定 ownership、持久 identity、带证据的 effect 以及 fail-closed 恢复语义来约束它们。

## Core capabilities / 核心能力

- **Recursive system architecture / 递归系统架构** — explicit ownership, narrow public APIs, typed ports, and composition-time provider binding. / 显式 ownership、窄公共 API、typed port 与 composition-time provider binding。
- **Experiment infrastructure / 实验基础设施** — study, run, branch, task, variant, workload, checkpoint, resume, and reproducibility identities. / Study、Run、Branch、Task、Variant、Workload、Checkpoint、Resume 与可复现性身份。
- **Agent runtime / Agent 运行时** — participant, capability, action, memory, workflow, and execution boundaries without hidden global lookup. / Participant、Capability、Action、Memory、Workflow 与 Execution 边界，不依赖隐藏式全局查找。
- **Model infrastructure / 模型基础设施** — model catalogues, revisions, qualification, serving identities, request envelopes, and prompt bindings. / 模型目录、revision、qualification、serving identity、request envelope 与 prompt binding。
- **Environment infrastructure / 环境基础设施** — specification, lifecycle, readiness, observation, effects, snapshots, and recovery. / 环境规格、生命周期、readiness、observation、effect、snapshot 与 recovery。
- **Process and server runtime / 进程与服务器运行时** — supervision, sessions, toolchains, remote execution, lifecycle control, and journals. / 进程监管、session、toolchain、远程执行、生命周期控制与 journal。
- **Durable data and artifacts / 持久数据与产物** — checksummed state, WAL-backed recovery, lineage, retention, and content-addressed evidence. / 校验和状态、WAL 恢复、lineage、retention 与内容寻址证据。
- **Reliability / 可靠性** — classified failures, effect certainty, reconciliation, replay, incident handling, and fail-closed recovery. / 故障分类、effect certainty、reconciliation、replay、incident 处理与 fail-closed 恢复。
- **Observability / 可观测性** — structured logs, events, metrics, traces, diagnostics, projections, and health signals. / 结构化日志、事件、指标、trace、diagnostic、projection 与健康信号。
- **Governance / 治理** — architecture, dependency, algorithm, concurrency, performance, forensic, release, and no-degradation gates. / 架构、依赖、算法、并发、性能、取证、发布与 no-degradation gate。

## Architecture / 架构

The platform separates composition, execution, and observation. / 平台将组合、执行与观测明确分离：

```text
system topology / contracts
          │
          ▼
composition root ── freezes provider identities and bindings
          │
          ▼
runtime execution ── uses only injected narrow ports
          │
          ▼
observation plane ── logs, metrics, traces, diagnostics, evidence
```
The central dependency rule is simple. / 核心依赖规则很简单：

```text
parent system
  └─ composes direct children through public contracts
       └─ runtime receives only the exact capability port it needs
```

Runtime code does not discover providers from a global service locator. Observability does not become a second command bus. Durable state has one owner, and external effects remain `CONFIRMED`, `REJECTED`, or `UNKNOWN` until reconciliation proves otherwise.

Runtime 不通过全局 service locator 发现 provider；Observability 不会变成第二条命令总线；每份 durable state 只有一个 owner；外部 effect 在 reconciliation 给出证据前保持 `CONFIRMED`、`REJECTED` 或 `UNKNOWN`。

The authoritative topology is `research_platform/governance/system_registry/catalog.json`. See [Platform Architecture](docs/architecture/PLATFORM_ARCHITECTURE.md) and the [documentation index](docs/INDEX.md).

权威系统拓扑位于 `research_platform/governance/system_registry/catalog.json`。完整设计请参阅 [Platform Architecture](docs/architecture/PLATFORM_ARCHITECTURE.md) 与 [documentation index](docs/INDEX.md)。

## Platform vs. downstream projects / 平台与下游项目

This repository is an independent reusable platform package. Research methods, benchmark tasks, project-specific environment composition, experiment matrices, model choices, deployment inventories, and scientific interpretation belong in **downstream repositories**.

本仓库是一个独立的可复用平台包。研究方法、benchmark task、项目专属环境组合、实验矩阵、模型选择、部署清单和科学解释应位于**下游仓库**。

Reusable providers may live upstream when they are independently useful across projects; Minecraft is one first-party example. / 当 provider 能跨项目独立复用时可以留在上游；Minecraft 是一个第一方示例。

```text
agent-research-platform
        │
        ├── install as a dependency / 作为依赖安装
        └── fork as a platform baseline / 作为平台基线 fork
                 │
                 ▼
       downstream research repository / 下游科研仓库
```
Downstream code consumes platform contracts and supplies project-owned implementations. The platform must not import downstream projects to decide scientific meaning, task semantics, model policy, or deployment policy.

下游代码消费平台 contract，并提供项目自身拥有的 implementation。平台不得通过导入下游项目来决定科学语义、任务语义、模型策略或部署策略。

## Quick start / 快速开始

### Requirements / 环境要求

- Python 3.11 or newer / Python 3.11 或更高版本
- Git
- Docker / Docker Compose for containerized workflows / 容器化工作流需要 Docker / Docker Compose
- Optional external runtimes only for providers that explicitly require them / 仅在特定 provider 明确需要时安装额外 runtime

### Install for development / 开发安装

```bash
git clone git@github.com:SDFGAEV/agent-research-platform-system.git
cd agent-research-platform-system

python -m venv .venv
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
python -m pip install -e ".[test]"
```

### Inspect the platform / 检查平台

```bash
research-platform-architecture-gate
research-platform-algorithm --help
research-platform-concurrency --help
research-platform-performance --help
research-platform-manage --help
```
## Container workflow / 容器工作流

A reusable Linux image and Compose definition are maintained under `deploy/`. / `deploy/` 中维护可复用的 Linux image 与 Compose 定义。

```bash
cp deploy/.env.example deploy/.env
docker compose -f deploy/compose.yaml config
docker compose -f deploy/compose.yaml build
docker compose -f deploy/compose.yaml run --rm platform-runtime doctor
```

The deployment layer separates immutable software from mutable runtime state. Host-specific paths and secrets belong in ignored environment/profile files, not committed composition code.

部署层将不可变软件与可变 runtime state 分离。主机专属路径和 secret 应放在被忽略的 environment/profile 文件中，而不是提交到 composition code。

For reproducible fleet deployment, build an immutable image once, bind it to an exact source revision, and reuse the same image identity across execution nodes instead of rebuilding independently on every host.

为保证集群部署可复现，应只构建一次不可变 image，将其绑定到 exact source revision，并在各执行节点复用同一 image identity，而不是每台机器独立重建。

### Bundled Minecraft provider / 内置 Minecraft Provider

Minecraft is a first-party reusable environment provider. The base image stays lightweight; enable the optional overlay only when Java/Node/Mineflayer support is required.

Minecraft 是第一方可复用环境 provider。基础 image 保持轻量，仅在需要 Java/Node/Mineflayer 时启用可选 overlay。

```bash
docker compose -f deploy/compose.yaml -f deploy/compose.minecraft.yaml build platform-runtime
docker compose -f deploy/compose.yaml -f deploy/compose.minecraft.yaml run --rm platform-runtime minecraft-doctor
```

Task suites, benchmark manifests, and scientific composition stay downstream. / Task suite、benchmark manifest 与科研 composition 仍属于下游项目。

See [Minecraft infrastructure](docs/infrastructure/minecraft/README.md). / 参阅 [Minecraft infrastructure](docs/infrastructure/minecraft/README.md)。

## Repository layout / 仓库结构
| Path / 路径 | Responsibility / 职责 |
| --- | --- |
| `research_platform/` | Reusable platform implementation and public system boundaries / 可复用平台实现与公共系统边界 |
| `configs/` | Versioned configuration examples and non-secret templates / 版本化配置示例与非 secret 模板 |
| `deploy/` | Container image, Compose runtime, and deployment bootstrap assets / 容器 image、Compose runtime 与部署引导资源 |
| `docs/` | Architecture, infrastructure, governance, status, and history / 架构、基础设施、治理、状态与历史文档 |
| `scripts/` | Thin operator, audit, release, maintenance, and development entry points / 轻量 operator、审计、发布、维护与开发入口 |
| `tests/` | Hierarchical regression and contract tests / 分层回归测试与 contract test |
| `research_platform/environment/minecraft/` | Reusable Minecraft provider; project task suites stay downstream / 可复用 Minecraft provider；项目 task suite 留在下游 |
| `build/` | Local/generated build outputs / 本地或生成的构建产物 |

The reusable package boundary is `research_platform/`. Project-specific code should originate in or migrate to downstream repositories rather than becoming a dependency of the platform core.

可复用 package 边界是 `research_platform/`。项目专属代码应在下游仓库中产生或迁移到下游，而不应成为平台核心的依赖。

## Root-level repository artifacts / 根目录仓库产物

Some tracked root files are public entry points or frozen release/validation projections. / 部分根目录文件是公共入口，或冻结的 release/validation projection。

| File / 文件 | Purpose / 用途 |
| --- | --- |
| `README.md` | Public GitHub entry point / GitHub 公共入口 |
| `LICENSE` | Apache License 2.0 legal text / Apache License 2.0 法律原文 |
| `NOTICE` | Repository attribution and notice information / 仓库 attribution 与 notice 信息 |
| `THIRD_PARTY_NOTICES.md` | Third-party licensing overview / 第三方许可概览 |
| `CONTEXT.md` | Platform vocabulary and navigation aid / 平台术语与导航 |
| `CURRENT_VALIDATION.json` | Checked-in validation snapshot / 提交到仓库的 validation 快照 |
| `RELEASE_MANIFEST.json` | Frozen release file manifest / 冻结的 release 文件清单 |
| `RELEASE_EVIDENCE.json` | Frozen regression and governance evidence / 冻结的回归与治理证据 |
| `RELEASE_AUTHORITY.json` | Digests binding release manifest and evidence / 绑定 release manifest 与 evidence 的 digest |
| `ALGORITHM_SCAN.md` | Root compatibility projection for release-manifest stability / 为 release manifest 稳定性保留的兼容 projection |
| `CONCURRENCY_SCAN.md` | Root compatibility projection for release-manifest stability / 为 release manifest 稳定性保留的兼容 projection |
| `PERF_SCAN.md` | Root compatibility projection for release-manifest stability / 为 release manifest 稳定性保留的兼容 projection |
| `pyproject.toml` | Python package metadata, dependencies, and console entry points / Python 包元数据、依赖与 CLI 入口 |
| `tests_support.py` | Shared repository test support / 仓库共享测试支持 |

Current governance reports belong under `docs/status/`. Root scan files are not live authority unless regenerated for the exact release being inspected.

当前治理报告位于 `docs/status/`。除非针对正在检查的 exact release 重新生成，否则根目录 scan 文件不应被视为当前 authority。

## Testing and verification / 测试与验证

Run the regression suite. / 运行回归测试：

```bash
python -m pytest -q
```

Run architecture and governance checks. / 运行架构与治理检查：

```bash
python scripts/architecture_gate.py
python scripts/public_contract_audit.py
python scripts/no_degradation_audit.py
research-platform-algorithm scan
research-platform-concurrency scan
research-platform-performance scan
```

The repository maintains a hierarchical test taxonomy in `tests/TEST_SYSTEM.json`; `scripts/test_system.py` validates that tests remain assigned to explicit subsystem/contract levels.

仓库通过 `tests/TEST_SYSTEM.json` 维护分层测试 taxonomy，并由 `scripts/test_system.py` 校验每个测试都归属于显式 subsystem/contract level。

Historical validation does not prove the current working tree. Re-run the gates for the exact revision you intend to publish or deploy.

历史 validation 不能证明当前 working tree。准备发布或部署哪个 exact revision，就应重新运行对应 gate。

## Design principles / 设计原则
1. **One owner per durable state / 每份持久状态只有一个 owner。** Projections may accelerate reads but do not silently become authorities. / Projection 可以加速读取，但不能悄悄变成 authority。
2. **Composition before execution / 先组合，后执行。** Provider selection is explicit and frozen before the runtime hot path. / Provider 选择必须显式完成，并在 runtime hot path 前冻结。
3. **Narrow runtime ports / 窄运行时端口。** Consumers receive only the capability they need, never a universal service locator. / Consumer 只获得需要的 capability，不获得万能 service locator。
4. **External effects are evidence-bearing / 外部副作用必须携带证据。** Timeout does not prove whether an effect happened. / Timeout 不能证明副作用发生或未发生。
5. **Recovery is identity-aware / 恢复必须感知 identity。** Resume requires compatible source, configuration, provider, checkpoint, and environment identities. / Resume 需要兼容的 source、configuration、provider、checkpoint 与 environment identity。
6. **No silent degradation / 禁止静默降级。** Do not lower quality, skip evidence, change providers, or weaken contracts merely to make a run succeed. / 不能为了让运行成功而降低质量、跳过证据、替换 provider 或弱化 contract。
7. **Observation is not authority / 观测不是 authority。** Logs, metrics, traces, and diagnostics describe execution; they do not secretly control it. / 日志、指标、trace 和 diagnostic 用于描述执行，不应暗中控制执行。
8. **Performance preserves semantics / 性能优化必须保持语义。** If an optimization can change externally visible or scientific values, it is a semantic change. / 如果优化可能改变外部可见值或科学结果，它就是语义变更。
9. **Documentation moves with implementation / 文档与实现同步演进。** Material code/configuration changes update owner documentation in the same change set. / 实质性代码或配置变更必须在同一 change set 中更新 owner 文档。
10. **Projects stay downstream / 项目语义留在下游。** Project-specific scientific meaning must not leak into reusable platform contracts. / 项目专属科学语义不得泄漏到可复用平台 contract。

## Extending the platform / 扩展平台

Add a new capability at the smallest owning boundary. / 在最小且正确的 owner 边界增加新能力：

```text
<system>/
├── api/          public contracts and identities / 公共 contract 与 identity
├── runtime/      lifecycle and execution semantics / 生命周期与执行语义
├── providers/    replaceable adapters owned by the system / 系统拥有的可替换 adapter
└── composition/  provider-to-port binding / provider 到 port 的绑定
```

Prefer a new provider when the contract already exists. Add a new contract only when the capability itself is new. Avoid generic wrappers that hide unrelated algorithms or external effects behind one interface.

已有 contract 能表达能力时优先新增 provider；只有能力本身是新的才新增 contract。避免用通用 wrapper 把无关算法或外部 effect 隐藏在同一接口之后。

## Documentation / 文档

Start with the [documentation index](docs/INDEX.md). / 从 [documentation index](docs/INDEX.md) 开始阅读。
Key references / 关键文档：

- [Platform architecture](docs/architecture/PLATFORM_ARCHITECTURE.md)
- [Detailed system map](docs/architecture/VNEXT_DETAILED_SYSTEM_MAP.md)
- [Final architecture migration contract](docs/architecture/FINAL_ARCHITECTURE_MIGRATION_CONTRACT.md)
- [Infrastructure documentation](docs/infrastructure/README.md)
- [Governance documentation](docs/governance/README.md)
- [Documentation change policy](docs/governance/DOCUMENTATION_CHANGE_POLICY.md)
- [Algorithm governance report](docs/status/algorithm/ALGORITHM_REPORT.md)
- [Concurrency governance report](docs/status/concurrency/CONCURRENCY_REPORT.md)
- [Performance governance report](docs/status/performance/PERFORMANCE_REPORT.md)
- [Historical engineering rounds](docs/history/README.md)

Architecture documents define reusable ownership and contracts. Status documents describe the current development tree. Historical documents preserve evidence for the state that existed when they were written.

Architecture 文档定义可复用 ownership 与 contract；Status 文档描述当前开发树；Historical 文档保存其撰写时对应状态的不可变工程证据。

## Security and configuration / 安全与配置

- Never commit passwords, private keys, access tokens, runtime secrets, or machine-local credentials. / 禁止提交密码、私钥、access token、runtime secret 或机器本地凭据。
- Keep host-specific paths and secrets in ignored local profiles or environment-bound stores. / 主机专属路径与 secret 放在忽略的本地 profile 或环境绑定存储中。
- Prefer key/agent-based unattended authentication for remote automation. / 远程自动化优先使用 key/agent-based 无人值守认证。
- Keep external-effect commands typed, bounded, journaled, and attributable to an operation identity. / 外部 effect 命令必须 typed、bounded、journaled，并可归因到 operation identity。
- Treat logs and evidence as potentially sensitive operational data. / 将日志与 evidence 视为潜在敏感运维数据。

## Contributing / 贡献

Changes should be small enough to review by ownership boundary and must include the tests and documentation required to prove the change.

变更应足够聚焦，使其可以按 ownership boundary 审查，并必须包含证明该变更所需的测试和文档。

Before opening a pull request / 提交 PR 前：

```bash
python -m pytest -q
python scripts/architecture_gate.py
```

For governed hot paths, also run the relevant algorithm, concurrency, performance, forensic, or release checks. / 对受治理的 hot path，还应运行对应的算法、并发、性能、取证或发布检查。

A contribution is expected to / 一个合格贡献应当：

- preserve system ownership and public-contract boundaries / 保持系统 ownership 与公共 contract 边界；
- add or update focused regression coverage / 添加或更新聚焦的回归覆盖；
- update the owning documentation in the same change set / 在同一 change set 更新 owner 文档；
- avoid unrelated refactors in the same commit / 避免在同一 commit 混入无关重构；
- preserve fail-closed behavior for uncertain external effects / 对不确定外部 effect 保持 fail-closed；
- document intentional semantic or compatibility changes explicitly / 显式记录有意的语义或兼容性变化。

See [Documentation Change Policy](docs/governance/DOCUMENTATION_CHANGE_POLICY.md). / 参阅 [Documentation Change Policy](docs/governance/DOCUMENTATION_CHANGE_POLICY.md)。

## License / 许可证

Agent Research Platform is licensed under the **Apache License, Version 2.0**. Apache-2.0 permits academic, open-source, internal, and commercial use while providing an explicit patent grant and preserving required notices.

Agent Research Platform 采用 **Apache License, Version 2.0**。Apache-2.0 允许学术研究、开源项目、内部基础设施和商业使用，同时提供明确的专利授权并要求保留必要 notice。

See [`LICENSE`](LICENSE) for the authoritative legal text and [`NOTICE`](NOTICE) for attribution information. Third-party components remain subject to their own licenses; see [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

权威法律文本见 [`LICENSE`](LICENSE)，attribution 信息见 [`NOTICE`](NOTICE)。第三方组件继续受其各自许可证约束，参阅 [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)。

Software, model weights, datasets, benchmark assets, and other independently distributed artifacts may carry separate license terms when explicitly stated. / 软件、模型权重、数据集、benchmark 资产以及其他独立分发的产物，在明确说明时可以采用各自独立的许可条款。

## Development status / 开发状态

The platform is under active architectural and runtime development. Historical changes are kept in `docs/history/`; current development truth belongs in `docs/status/` and must be verified against the exact revision being used.

平台仍处于持续的架构与 runtime 开发中。历史变化保存在 `docs/history/`；当前开发状态以 `docs/status/` 为准，并应针对实际使用的 exact revision 重新验证。

For production, publication, or scientific claims, do not rely on a historical green result alone: rerun the relevant gates and inspect the release evidence bound to the exact source revision. / 对生产、发布或科学结论，不应仅依赖历史绿灯；请对 exact source revision 重新运行相关 gate，并检查与该 revision 绑定的 release evidence。
