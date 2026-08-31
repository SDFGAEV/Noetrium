# Noetrium: Reproducible Research Infrastructure for AI Agents



<!-- readme-nav:start -->
<p align="center">
  <a href="README.md">English</a> ·
  <a href="README.zh-CN.md">简体中文</a> ·
  <strong>繁體中文</strong> ·
  <a href="README.ja.md">日本語</a> ·
  <a href="README.ko.md">한국어</a> ·
  <a href="README.es.md">Español</a> ·
  <a href="README.pt-BR.md">Português (Brasil)</a> ·
  <a href="README.fr.md">Français</a> ·
  <a href="README.de.md">Deutsch</a> ·
  <a href="README.ru.md">Русский</a>
</p>
<!-- readme-nav:end -->



<!-- readme-locale:zh-TW -->

<!-- readme-source-sha256:9dd7f68d71e7c6bfc9c059ec68315c5e86dc1ccac0a179645d1e0879c40c283f -->



**面向可重現 AI Agent 研究的契約驅動基礎設施。**



[![Python](https://img.shields.io/badge/Python-%3E%3D3.11-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Version](https://img.shields.io/badge/version-0.43.1-blue)](pyproject.toml)
[![Architecture](https://img.shields.io/badge/architecture-contract--driven-6f42c1)](docs/architecture/PLATFORM_ARCHITECTURE.md)
[![License](https://img.shields.io/badge/license-Apache--2.0-green)](LICENSE)



<!-- readme-section:overview -->

## 專案概覽

Noetrium 是一個與具體專案解耦的平台，用於建構、執行、復原、觀測、最佳化與稽核長時間運行的 AI Agent 系統與研究工作負載。

可重用基礎設施留在平台層；論文特定的科學語義、benchmark 選擇、實驗矩陣與部署策略留在下游專案。

<!-- readme-section:why -->

## 為什麼需要這個平台？

長時間運行的 Agent 系統比一般腳本有更多失效方式：程序可能崩潰、外部 effect 可能處於不確定狀態、環境會漂移、模型部署會改變、checkpoint 可能失配，不完整日誌也可能被誤認為有效證據。

平台將這些問題建模為顯式系統，並使用 typed contract、穩定 ownership、持久 identity、帶證據的 effect 與 fail-closed 復原語義。

<!-- readme-section:capabilities -->

## 核心能力

- 遞迴架構 — 顯式 ownership、窄公共 API、typed port 與 composition-time provider binding。
- 實驗基礎設施 — Study、Run、Branch、Task、Variant、Workload、Checkpoint、Resume 與可重現 identity。
- Agent 執行期 — Participant、Capability、Action、Memory、Workflow 與 Execution 邊界，不依賴隱藏的全域查找。
- 模型基礎設施 — catalog、revision、qualification、serving identity、request envelope 與 prompt binding。
- 環境基礎設施 — specification、生命週期、readiness、observation、effect、snapshot 與 recovery。
- 程序/伺服器執行期 — supervision、session、toolchain、遠端執行、生命週期控制與 journal。
- 持久資料/Artifact — checksum 狀態、WAL 復原、lineage、retention 與內容尋址證據。
- 可靠性 — 故障分類、effect certainty、reconciliation、replay、incident 與 fail-closed 復原。
- 可觀測性 — 結構化日誌、event、metric、trace、diagnostic、projection 與健康訊號。
- 治理 — architecture、dependency、algorithm、concurrency、performance、forensic、release 與 no-degradation gate。

<!-- readme-section:architecture -->

## 架構

Composition、Execution 與 Observation 是彼此分離的 authority plane。

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

Runtime 不透過全域 service locator 發現 provider；Observability 也不是第二條命令匯流排。每份 durable state 只有一個 owner；外部 effect 在 reconciliation 證明之前維持 UNKNOWN。

`research_platform/governance/system_registry/catalog.json`

<!-- readme-section:downstream -->

## 平台與下游專案

本儲存庫是可獨立重用的平台套件。研究方法、任務集、專案特定環境組合、實驗矩陣、模型選擇、部署清單與科學解釋都屬於下游專案。

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

下游程式碼消費平台公共 contract 並提供專案自有實作；平台不能反向 import 下游專案來決定科學語義或部署策略。

<!-- readme-section:quick-start -->

## 快速開始

### 環境要求

- Python 3.11 或更高版本
- Git
- 容器工作流程需要 Docker / Docker Compose
- 只有明確要求的 Provider 才需要額外外部執行期

### 開發安裝

```bash
git clone git@github.com:SDFGAEV/noetrium.git
cd noetrium
python -m venv .venv
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
```

### 檢查平台

```bash
research-platform-architecture-gate
research-platform-algorithm --help
research-platform-concurrency --help
research-platform-performance --help
research-platform-manage --help
```

<!-- readme-section:containers -->

## 容器工作流程

`deploy/` 下維護可重用 Linux 映像與 Compose 定義。

```bash
cp deploy/.env.example deploy/.env
docker compose -f deploy/compose.yaml config
docker compose -f deploy/compose.yaml build
docker compose -f deploy/compose.yaml run --rm platform-runtime doctor
```

部署層將不可變軟體與可變 runtime state 分離；主機路徑與 secret 不進入已提交的 composition 程式碼。

### 內建 Minecraft Provider

Minecraft 是第一方可重用環境 Provider；任務集與科學組合繼續留在下游。

```bash
docker compose -f deploy/compose.yaml -f deploy/compose.minecraft.yaml build platform-runtime
docker compose -f deploy/compose.yaml -f deploy/compose.minecraft.yaml run --rm platform-runtime minecraft-doctor
```

[Minecraft infrastructure](docs/infrastructure/minecraft/README.md)

<!-- readme-section:repository-layout -->

## 儲存庫結構

| Path | Responsibility |
| --- | --- |
| `research_platform/` | 可重用平台實作與公共系統邊界 |
| `configs/` | 版本化設定範例與非機密模板 |
| `deploy/` | 容器映像、Compose runtime 與部署引導資產 |
| `docs/` | 架構、基礎設施、治理、狀態與歷史文件 |
| `scripts/` | 輕量 operator、audit、release 與維護入口 |
| `tests/` | 分層回歸與 contract 測試 |
| `research_platform/environment/minecraft/` | 內建可重用 Minecraft 環境 Provider |
| `LICENSE` / `NOTICE` / `THIRD_PARTY_NOTICES.md` | Apache-2.0 與第三方授權說明 |

`research_platform/` is the reusable package boundary; project-specific code stays downstream.

<!-- readme-section:testing -->

## 測試與驗證

針對正在評估的 exact revision 執行儲存庫回歸套件與治理 gate。

```bash
python -m pytest -q
python scripts/architecture_gate.py
python scripts/public_contract_audit.py
python scripts/no_degradation_audit.py
python scripts/check_readme_i18n.py
```

歷史綠燈不能證明目前工作樹。發布或部署前必須針對準備使用的 exact revision 重新執行相關 gate。

儲存庫使用分層測試 taxonomy，使每個測試都歸屬於明確 contract level，並讓 release evidence 能證明實際執行了什麼。 See `tests/TEST_SYSTEM.json`.

<!-- readme-section:principles -->

## 設計原則

1. 每份 durable state 只有一個 owner。
2. 先 composition，後 execution。
3. Runtime port 必須保持窄介面。
4. 外部 effect 必須攜帶證據。
5. 復原必須感知 identity。
6. 禁止靜默降級。
7. Observation 不是 authority。
8. 效能最佳化必須保持語義。
9. 實作變化必須同步文件。
10. 專案特定語義必須留在下游。

<!-- readme-section:extending -->

## 擴充平台

在最小 owner 邊界增加能力。已有公共 contract 時優先新增 provider；只有能力本身新增時才增加新 contract。

```text
<system>/
├── api/          public contracts and identities
├── runtime/      lifecycle and execution semantics
├── providers/    replaceable adapters owned by the system
└── composition/  provider-to-port binding
```

避免用通用 wrapper 把無關演算法、provider discovery 或外部 effect 隱藏在一個介面後面。

<!-- readme-section:documentation -->

## 文件

從文件索引開始。

### 關鍵參考文件

- [Documentation index](docs/INDEX.md)
- [Platform architecture](docs/architecture/PLATFORM_ARCHITECTURE.md)
- [Detailed system map](docs/architecture/VNEXT_DETAILED_SYSTEM_MAP.md)
- [Architecture migration contract](docs/architecture/FINAL_ARCHITECTURE_MIGRATION_CONTRACT.md)
- [Infrastructure documentation](docs/infrastructure/README.md)
- [Governance documentation](docs/governance/README.md)
- [Current status](docs/status/README.md)
- [Engineering history](docs/history/README.md)

架構文件定義可重用 ownership 與 contract；status 文件描述目前開發樹；history 保存其寫入時刻對應狀態的證據。

<!-- readme-section:security -->

## 安全與設定

- 禁止提交密碼、私鑰、token、runtime secret 或機器本地憑證。
- 主機路徑與 secret 放在忽略的本地 profile 或環境綁定儲存中。
- 遠端自動化優先使用 key/agent 無人值守認證。
- 外部 effect 命令必須 typed、bounded、journaled 並綁定 operation identity。
- 日誌與 evidence 應視為可能包含敏感維運資訊。

<!-- readme-section:contributing -->

## 貢獻指南

變更應能按 ownership boundary 審查，並包含證明該變更所需的測試與文件。

### 提交 Pull Request 前

```bash
python -m pytest -q
python scripts/architecture_gate.py
python scripts/check_readme_i18n.py
```

- 保持 system ownership 與公共 contract 邊界
- 增加或更新聚焦的回歸覆蓋
- 在同一 change set 更新 owner 文件
- 避免在同一 commit 混入無關重構
- 對不確定外部 effect 保持 fail-closed
- 明確記錄有意的語義或相容性變化

[Documentation Change Policy](docs/governance/DOCUMENTATION_CHANGE_POLICY.md)

<!-- readme-section:license -->

## 授權條款

Noetrium 採用 Apache License 2.0。具有法律效力的權威文本是儲存庫根目錄的 LICENSE。

第三方元件繼續受各自授權條款約束，詳見 THIRD_PARTY_NOTICES.md；獨立散布的模型權重、資料集或 benchmark 資產可以另行聲明授權條款。

[`LICENSE`](LICENSE) · [`NOTICE`](NOTICE) · [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)

<!-- readme-section:status -->

## 開發狀態

平台仍處於持續的架構與 runtime 開發階段。

對於生產、發布或科學結論，必須重新執行相關 gate，並檢查與 exact source revision 綁定的 release evidence，而不能只依賴歷史綠燈。

歷史變更有意不寫入這份 README；不可變的工程記錄請查看 `docs/history/`。

目前開發事實以 `docs/status/CURRENT_DEVELOPMENT_BASELINE.md` 為準；發布與科研結論必須綁定到被評估精確版本的證據。

`docs/status/` · `docs/history/`
