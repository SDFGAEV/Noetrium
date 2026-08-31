# Noetrium: Reproducible Research Infrastructure for AI Agents



<!-- readme-nav:start -->
<p align="center">
  <a href="README.md">English</a> ·
  <strong>简体中文</strong> ·
  <a href="README.zh-TW.md">繁體中文</a> ·
  <a href="README.ja.md">日本語</a> ·
  <a href="README.ko.md">한국어</a> ·
  <a href="README.es.md">Español</a> ·
  <a href="README.pt-BR.md">Português (Brasil)</a> ·
  <a href="README.fr.md">Français</a> ·
  <a href="README.de.md">Deutsch</a> ·
  <a href="README.ru.md">Русский</a>
</p>
<!-- readme-nav:end -->



<!-- readme-locale:zh-CN -->

<!-- readme-source-sha256:9dd7f68d71e7c6bfc9c059ec68315c5e86dc1ccac0a179645d1e0879c40c283f -->



**面向可复现 AI Agent 研究的契约驱动基础设施。**



[![Python](https://img.shields.io/badge/Python-%3E%3D3.11-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Version](https://img.shields.io/badge/version-0.43.1-blue)](pyproject.toml)
[![Architecture](https://img.shields.io/badge/architecture-contract--driven-6f42c1)](docs/architecture/PLATFORM_ARCHITECTURE.md)
[![License](https://img.shields.io/badge/license-Apache--2.0-green)](LICENSE)



<!-- readme-section:overview -->

## 项目概览

Noetrium 是一个与具体项目解耦的平台，用于构建、运行、恢复、观测、优化和审计长时运行的 AI Agent 系统与研究工作负载。

可复用基础设施留在平台层；论文特定的科学语义、benchmark 选择、实验矩阵和部署策略留在下游项目。

<!-- readme-section:why -->

## 为什么需要这个平台？

长时运行的 Agent 系统比普通脚本有更多失效方式：进程可能崩溃，外部 effect 可能处于不确定状态，环境会漂移，模型部署会变化，checkpoint 可能失配，不完整日志也可能被误当作有效证据。

平台把这些问题建模为显式系统，并使用 typed contract、稳定 ownership、持久 identity、带证据的 effect 与 fail-closed 恢复语义。

<!-- readme-section:capabilities -->

## 核心能力

- 递归架构 — 显式 ownership、窄公共 API、typed port 与 composition-time provider binding。
- 实验基础设施 — Study、Run、Branch、Task、Variant、Workload、Checkpoint、Resume 与可复现 identity。
- Agent 运行时 — Participant、Capability、Action、Memory、Workflow 与 Execution 边界，不依赖隐藏的全局查找。
- 模型基础设施 — catalog、revision、qualification、serving identity、request envelope 与 prompt binding。
- 环境基础设施 — specification、生命周期、readiness、observation、effect、snapshot 与 recovery。
- 进程/服务器运行时 — supervision、session、toolchain、远程执行、生命周期控制与 journal。
- 持久数据/Artifact — checksum 状态、WAL 恢复、lineage、retention 与内容寻址证据。
- 可靠性 — 故障分类、effect certainty、reconciliation、replay、incident 与 fail-closed 恢复。
- 可观测性 — 结构化日志、event、metric、trace、diagnostic、projection 与健康信号。
- 治理 — architecture、dependency、algorithm、concurrency、performance、forensic、release 与 no-degradation gate。

<!-- readme-section:architecture -->

## 架构

Composition、Execution 与 Observation 是彼此分离的 authority plane。

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

Runtime 不通过全局 service locator 发现 provider；Observability 也不是第二条命令总线。每份 durable state 只有一个 owner；外部 effect 在 reconciliation 证明之前保持 UNKNOWN。

`research_platform/governance/system_registry/catalog.json`

<!-- readme-section:downstream -->

## 平台与下游项目

本仓库是可独立复用的平台包。研究方法、任务集、项目特定环境组合、实验矩阵、模型选择、部署清单和科学解释都属于下游项目。

```text
noetrium
        │
        ├── install as a dependency, or
        └── fork as a platform baseline
                 │
                 ▼
       downstream research repository
       ├── project-specific method
       ├── experiment composition
       ├── task/environment bindings
       └── project evidence and results
```

下游代码消费平台公共 contract 并提供项目自有实现；平台不能反向 import 下游项目来决定科学语义或部署策略。

<!-- readme-section:quick-start -->

## 快速开始

### 环境要求

- Python 3.11 或更高版本
- Git
- 容器工作流需要 Docker / Docker Compose
- 只有明确要求的 Provider 才需要额外外部运行时

### 开发安装

```bash
git clone git@github.com:SDFGAEV/noetrium.git
cd noetrium
python -m venv .venv
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
```

### 检查平台

```bash
research-platform-architecture-gate
research-platform-algorithm --help
research-platform-concurrency --help
research-platform-performance --help
research-platform-manage --help
```

<!-- readme-section:containers -->

## 容器工作流

`deploy/` 下维护可复用 Linux 镜像与 Compose 定义。

```bash
cp deploy/.env.example deploy/.env
docker compose -f deploy/compose.yaml config
docker compose -f deploy/compose.yaml build
docker compose -f deploy/compose.yaml run --rm platform-runtime doctor
```

部署层把不可变软件与可变 runtime state 分离；主机路径和 secret 不进入已提交的 composition 代码。

### 内置 Minecraft Provider

Minecraft 是第一方可复用环境 Provider；任务集和科学组合继续留在下游。

```bash
docker compose -f deploy/compose.yaml -f deploy/compose.minecraft.yaml build platform-runtime
docker compose -f deploy/compose.yaml -f deploy/compose.minecraft.yaml run --rm platform-runtime minecraft-doctor
```

[Minecraft infrastructure](docs/infrastructure/minecraft/README.md)

<!-- readme-section:repository-layout -->

## 仓库结构

| Path | Responsibility |
| --- | --- |
| `research_platform/` | 可复用平台实现与公共系统边界 |
| `configs/` | 版本化配置示例与非机密模板 |
| `deploy/` | 容器镜像、Compose runtime 与部署引导资产 |
| `docs/` | 架构、基础设施、治理、状态与历史文档 |
| `scripts/` | 轻量 operator、audit、release 与维护入口 |
| `tests/` | 分层回归与 contract 测试 |
| `research_platform/environment/minecraft/` | 内置可复用 Minecraft 环境 Provider |
| `LICENSE` / `NOTICE` / `THIRD_PARTY_NOTICES.md` | Apache-2.0 与第三方许可说明 |

`research_platform/` is the reusable package boundary; project-specific code stays downstream.

<!-- readme-section:testing -->

## 测试与验证

针对正在评估的 exact revision 运行仓库回归套件与治理 gate。

```bash
python -m pytest -q
python scripts/architecture_gate.py
python scripts/public_contract_audit.py
python scripts/no_degradation_audit.py
python scripts/check_readme_i18n.py
```

历史绿灯不能证明当前工作树。发布或部署前必须针对准备使用的 exact revision 重新运行相关 gate。

仓库使用分层测试 taxonomy，使每个测试都归属于明确 contract level，并让 release evidence 能证明实际执行了什么。 See `tests/TEST_SYSTEM.json`.

<!-- readme-section:principles -->

## 设计原则

1. 每份 durable state 只有一个 owner。
2. 先 composition，后 execution。
3. Runtime port 必须保持窄接口。
4. 外部 effect 必须携带证据。
5. 恢复必须感知 identity。
6. 禁止静默降级。
7. Observation 不是 authority。
8. 性能优化必须保持语义。
9. 实现变化必须同步文档。
10. 项目特定语义必须留在下游。

<!-- readme-section:extending -->

## 扩展平台

在最小 owner 边界增加能力。已有公共 contract 时优先新增 provider；只有能力本身新增时才增加新 contract。

```text
<system>/
├── api/          public contracts and identities
├── runtime/      lifecycle and execution semantics
├── providers/    replaceable adapters owned by the system
└── composition/  provider-to-port binding
```

避免用通用 wrapper 把无关算法、provider discovery 或外部 effect 隐藏在一个接口后面。

<!-- readme-section:documentation -->

## 文档

从文档索引开始。

### 关键参考文档

- [Documentation index](docs/INDEX.md)
- [Platform architecture](docs/architecture/PLATFORM_ARCHITECTURE.md)
- [Detailed system map](docs/architecture/VNEXT_DETAILED_SYSTEM_MAP.md)
- [Architecture migration contract](docs/architecture/FINAL_ARCHITECTURE_MIGRATION_CONTRACT.md)
- [Infrastructure documentation](docs/infrastructure/README.md)
- [Governance documentation](docs/governance/README.md)
- [Current status](docs/status/README.md)
- [Engineering history](docs/history/README.md)

架构文档定义可复用 ownership 与 contract；status 文档描述当前开发树；history 保存其写入时刻对应状态的证据。

<!-- readme-section:security -->

## 安全与配置

- 禁止提交密码、私钥、token、runtime secret 或机器本地凭据。
- 主机路径与 secret 放在忽略的本地 profile 或环境绑定存储中。
- 远程自动化优先使用 key/agent 无人值守认证。
- 外部 effect 命令必须 typed、bounded、journaled 并绑定 operation identity。
- 日志与 evidence 应视为可能包含敏感运维信息。

<!-- readme-section:contributing -->

## 贡献指南

变更应能按 ownership boundary 审查，并包含证明该变更所需的测试与文档。

### 提交 Pull Request 前

```bash
python -m pytest -q
python scripts/architecture_gate.py
python scripts/check_readme_i18n.py
```

- 保持 system ownership 与公共 contract 边界
- 增加或更新聚焦的回归覆盖
- 在同一 change set 更新 owner 文档
- 避免在同一 commit 混入无关重构
- 对不确定外部 effect 保持 fail-closed
- 明确记录有意的语义或兼容性变化

[Documentation Change Policy](docs/governance/DOCUMENTATION_CHANGE_POLICY.md)

<!-- readme-section:license -->

## 许可证

Noetrium 采用 Apache License 2.0。具有法律效力的权威文本是仓库根目录的 LICENSE。

第三方组件继续受各自许可证约束，详见 THIRD_PARTY_NOTICES.md；独立分发的模型权重、数据集或 benchmark 资产可以另行声明许可条款。

[`LICENSE`](LICENSE) · [`NOTICE`](NOTICE) · [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)

<!-- readme-section:status -->

## 开发状态

平台仍处于持续的架构与 runtime 开发阶段。

对于生产、发布或科学结论，必须重新运行相关 gate，并检查与 exact source revision 绑定的 release evidence，而不能只依赖历史绿灯。

历史变更有意不写入这份 README；不可变的工程记录请查看 `docs/history/`。

当前开发事实以 `docs/status/CURRENT_DEVELOPMENT_BASELINE.md` 为准；发布与科研结论必须绑定到被评估精确版本的证据。

`docs/status/` · `docs/history/`
