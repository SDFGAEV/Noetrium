# Noetrium: Reproducible Research Infrastructure for AI Agents



<!-- readme-nav:start -->
<p align="center">
  <a href="README.md">English</a> ·
  <a href="README.zh-CN.md">简体中文</a> ·
  <a href="README.zh-TW.md">繁體中文</a> ·
  <strong>日本語</strong> ·
  <a href="README.ko.md">한국어</a> ·
  <a href="README.es.md">Español</a> ·
  <a href="README.pt-BR.md">Português (Brasil)</a> ·
  <a href="README.fr.md">Français</a> ·
  <a href="README.de.md">Deutsch</a> ·
  <a href="README.ru.md">Русский</a>
</p>
<!-- readme-nav:end -->



<!-- readme-locale:ja -->

<!-- readme-source-sha256:9dd7f68d71e7c6bfc9c059ec68315c5e86dc1ccac0a179645d1e0879c40c283f -->



**再現可能な AI エージェント研究のための契約駆動インフラストラクチャ。**



[![Python](https://img.shields.io/badge/Python-%3E%3D3.11-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Version](https://img.shields.io/badge/version-0.43.1-blue)](pyproject.toml)
[![Architecture](https://img.shields.io/badge/architecture-contract--driven-6f42c1)](docs/architecture/PLATFORM_ARCHITECTURE.md)
[![License](https://img.shields.io/badge/license-Apache--2.0-green)](LICENSE)



<!-- readme-section:overview -->

## 概要

Noetrium は、長時間稼働する AI エージェントシステムと研究ワークロードを構築・実行・復旧・観測・最適化・監査するための、プロジェクト非依存プラットフォームです。

再利用可能な基盤はプラットフォーム側に置き、論文固有の科学的意味、benchmark、実験行列、配備ポリシーは下流プロジェクトに置きます。

<!-- readme-section:why -->

## なぜこのプラットフォームが必要か

長時間稼働する Agent システムには通常のスクリプトより多くの障害形態があります。プロセス停止、外部 effect の不確実性、環境 drift、モデル配備の変更、checkpoint 不整合、不完全なログの誤認などです。

本プラットフォームはこれらを明示的なシステムとしてモデル化し、typed contract、安定した ownership、永続 identity、証拠を伴う effect、fail-closed な復旧セマンティクスを使用します。

<!-- readme-section:capabilities -->

## 主な機能

- 再帰的アーキテクチャ — 明示的 ownership、狭い公開 API、typed port、composition-time provider binding。
- 実験基盤 — Study、Run、Branch、Task、Variant、Workload、Checkpoint、Resume、再現性 identity。
- Agent runtime — Participant、Capability、Action、Memory、Workflow、Execution の境界。隠れたグローバル lookup は使用しません。
- モデル基盤 — catalog、revision、qualification、serving identity、request envelope、prompt binding。
- 環境基盤 — specification、lifecycle、readiness、observation、effect、snapshot、recovery。
- プロセス/サーバー runtime — supervision、session、toolchain、remote execution、lifecycle control、journal。
- 永続データ/Artifact — checksum 状態、WAL recovery、lineage、retention、content-addressed evidence。
- 信頼性 — failure classification、effect certainty、reconciliation、replay、incident、fail-closed recovery。
- 可観測性 — 構造化 log、event、metric、trace、diagnostic、projection、health signal。
- ガバナンス — architecture、dependency、algorithm、concurrency、performance、forensic、release、no-degradation gate。

<!-- readme-section:architecture -->

## アーキテクチャ

Composition、Execution、Observation は別々の authority plane として扱います。

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

Runtime はグローバル service locator から provider を探索しません。Observability も第二の command bus にはなりません。durable state には単一 owner があり、外部 effect は reconciliation で証明されるまで UNKNOWN のままです。

`research_platform/governance/system_registry/catalog.json`

<!-- readme-section:downstream -->

## プラットフォームと下流プロジェクト

このリポジトリは独立して再利用できるプラットフォームパッケージです。研究手法、タスク群、プロジェクト固有の環境構成、実験行列、モデル選択、配備 inventory、科学的解釈は下流に属します。

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

下流コードは公開 platform contract を利用してプロジェクト所有の実装を提供します。プラットフォームが下流プロジェクトを import して科学的意味や配備ポリシーを決めることはありません。

<!-- readme-section:quick-start -->

## クイックスタート

### 要件

- Python 3.11 以降
- Git
- コンテナワークフロー用 Docker / Docker Compose
- 明示的に必要とする Provider のみ追加 runtime が必要

### 開発用インストール

```bash
git clone git@github.com:SDFGAEV/noetrium.git
cd noetrium
python -m venv .venv
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
```

### プラットフォームの確認

```bash
research-platform-architecture-gate
research-platform-algorithm --help
research-platform-concurrency --help
research-platform-performance --help
research-platform-manage --help
```

<!-- readme-section:containers -->

## コンテナワークフロー

再利用可能な Linux image と Compose 定義は `deploy/` で管理します。

```bash
cp deploy/.env.example deploy/.env
docker compose -f deploy/compose.yaml config
docker compose -f deploy/compose.yaml build
docker compose -f deploy/compose.yaml run --rm platform-runtime doctor
```

Deployment 層は immutable software と mutable runtime state を分離し、host 固有 path と secret を commit 済み composition code に入れません。

### 同梱 Minecraft Provider

Minecraft は first-party の再利用可能な environment Provider です。Task suite と科学的 composition は downstream に残します。

```bash
docker compose -f deploy/compose.yaml -f deploy/compose.minecraft.yaml build platform-runtime
docker compose -f deploy/compose.yaml -f deploy/compose.minecraft.yaml run --rm platform-runtime minecraft-doctor
```

[Minecraft infrastructure](docs/infrastructure/minecraft/README.md)

<!-- readme-section:repository-layout -->

## リポジトリ構成

| Path | Responsibility |
| --- | --- |
| `research_platform/` | 再利用可能なプラットフォーム実装と公開システム境界 |
| `configs/` | バージョン管理された設定例と非機密テンプレート |
| `deploy/` | コンテナイメージ、Compose runtime、deployment bootstrap |
| `docs/` | Architecture、infrastructure、governance、status、history 文書 |
| `scripts/` | 薄い operator、audit、release、maintenance entry point |
| `tests/` | 階層型 regression / contract tests |
| `research_platform/environment/minecraft/` | 再利用可能な Minecraft environment provider |
| `LICENSE` / `NOTICE` / `THIRD_PARTY_NOTICES.md` | Apache-2.0 と第三者ライセンス通知 |

`research_platform/` is the reusable package boundary; project-specific code stays downstream.

<!-- readme-section:testing -->

## テストと検証

評価対象の exact revision に対して regression suite と governance gate を実行します。

```bash
python -m pytest -q
python scripts/architecture_gate.py
python scripts/public_contract_audit.py
python scripts/no_degradation_audit.py
python scripts/check_readme_i18n.py
```

過去の green result は現在の tree を証明しません。公開・配備する exact revision に対して必要な gate を再実行してください。

リポジトリは階層型 test taxonomy を使い、各テストを明示的な contract level に割り当て、release evidence が実際の検証範囲を証明できるようにします。 See `tests/TEST_SYSTEM.json`.

<!-- readme-section:principles -->

## 設計原則

1. durable state ごとに owner は一つ。
2. Execution より先に composition。
3. Runtime port は狭く保つ。
4. 外部 effect は evidence を持つ。
5. Recovery は identity-aware。
6. silent degradation を許さない。
7. Observation は authority ではない。
8. 性能最適化で意味を変えない。
9. 実装変更と文書更新を同時に行う。
10. プロジェクト固有意味は downstream に置く。

<!-- readme-section:extending -->

## プラットフォームの拡張

最小の owner boundary に機能を追加します。公開 contract が既にある場合は新しい provider を優先し、能力そのものが新しい場合のみ contract を追加します。

```text
<system>/
├── api/          public contracts and identities
├── runtime/      lifecycle and execution semantics
├── providers/    replaceable adapters owned by the system
└── composition/  provider-to-port binding
```

無関係な algorithm、provider discovery、外部 effect を一つの汎用 wrapper に隠さないでください。

<!-- readme-section:documentation -->

## ドキュメント

documentation index から開始してください。

### 主要リファレンス

- [Documentation index](docs/INDEX.md)
- [Platform architecture](docs/architecture/PLATFORM_ARCHITECTURE.md)
- [Detailed system map](docs/architecture/VNEXT_DETAILED_SYSTEM_MAP.md)
- [Architecture migration contract](docs/architecture/FINAL_ARCHITECTURE_MIGRATION_CONTRACT.md)
- [Infrastructure documentation](docs/infrastructure/README.md)
- [Governance documentation](docs/governance/README.md)
- [Current status](docs/status/README.md)
- [Engineering history](docs/history/README.md)

Architecture 文書は再利用可能な ownership と contract を定義し、status 文書は現在の開発 tree を表し、history は記録時点の状態証拠を保存します。

<!-- readme-section:security -->

## セキュリティと設定

- password、private key、access token、runtime secret、端末固有 credential を commit しない。
- host 固有 path と secret は無視対象 local profile または environment-bound store に置く。
- remote automation では key/agent ベースの無人認証を優先する。
- 外部 effect command は typed、bounded、journaled で operation identity に帰属させる。
- logs と evidence は機密運用データを含み得るものとして扱う。

<!-- readme-section:contributing -->

## コントリビューション

変更は ownership boundary 単位でレビュー可能にし、証明に必要な tests と documentation を含めます。

### Pull Request を作成する前に

```bash
python -m pytest -q
python scripts/architecture_gate.py
python scripts/check_readme_i18n.py
```

- system ownership と public-contract boundary を守る
- focused regression coverage を追加・更新する
- 同じ change set で owner 文書を更新する
- 同一 commit に無関係な refactor を混ぜない
- 不確実な外部 effect で fail-closed を守る
- 意図的な semantic/compatibility change を明示する

[Documentation Change Policy](docs/governance/DOCUMENTATION_CHANGE_POLICY.md)

<!-- readme-section:license -->

## ライセンス

Noetrium は Apache License 2.0 でライセンスされています。法的に権威のある本文はルートの LICENSE です。

第三者コンポーネントにはそれぞれのライセンスが適用されます。THIRD_PARTY_NOTICES.md を参照してください。独立配布されるモデル重み、データセット、benchmark 資産には別条件が設定される場合があります。

[`LICENSE`](LICENSE) · [`NOTICE`](NOTICE) · [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)

<!-- readme-section:status -->

## 開発状況

プラットフォームは現在もアーキテクチャと runtime の継続的な開発中です。

本番利用、公開、科学的主張では、古い green result に依存せず、関連 gate を再実行し exact source revision に結び付いた release evidence を確認してください。

履歴変更は意図的にこの README へ入れません。不変の engineering record は `docs/history/` を参照してください。

現在の開発上の正本は `docs/status/CURRENT_DEVELOPMENT_BASELINE.md` です。リリースや研究上の主張は、評価対象の正確なリビジョンに結び付いた証拠に基づく必要があります。

`docs/status/` · `docs/history/`
