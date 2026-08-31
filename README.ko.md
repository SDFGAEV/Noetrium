# Noetrium: Reproducible Research Infrastructure for AI Agents



<!-- readme-nav:start -->
<p align="center">
  <a href="README.md">English</a> ·
  <a href="README.zh-CN.md">简体中文</a> ·
  <a href="README.zh-TW.md">繁體中文</a> ·
  <a href="README.ja.md">日本語</a> ·
  <strong>한국어</strong> ·
  <a href="README.es.md">Español</a> ·
  <a href="README.pt-BR.md">Português (Brasil)</a> ·
  <a href="README.fr.md">Français</a> ·
  <a href="README.de.md">Deutsch</a> ·
  <a href="README.ru.md">Русский</a>
</p>
<!-- readme-nav:end -->



<!-- readme-locale:ko -->

<!-- readme-source-sha256:9dd7f68d71e7c6bfc9c059ec68315c5e86dc1ccac0a179645d1e0879c40c283f -->



**재현 가능한 AI 에이전트 연구를 위한 계약 중심 인프라.**



[![Python](https://img.shields.io/badge/Python-%3E%3D3.11-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Version](https://img.shields.io/badge/version-0.43.1-blue)](pyproject.toml)
[![Architecture](https://img.shields.io/badge/architecture-contract--driven-6f42c1)](docs/architecture/PLATFORM_ARCHITECTURE.md)
[![License](https://img.shields.io/badge/license-Apache--2.0-green)](LICENSE)



<!-- readme-section:overview -->

## 개요

Noetrium은 장시간 실행되는 AI 에이전트 시스템과 연구 워크로드를 구축, 실행, 복구, 관측, 최적화, 감사하기 위한 프로젝트 독립형 플랫폼입니다.

재사용 가능한 인프라는 플랫폼에 두고, 논문별 과학적 의미, benchmark 선택, 실험 행렬, 배포 정책은 downstream 프로젝트에 둡니다.

<!-- readme-section:why -->

## 왜 이 플랫폼인가?

장시간 실행되는 Agent 시스템은 일반 스크립트보다 더 많은 실패 모드를 가집니다. 프로세스 중단, 외부 effect의 불확실성, 환경 drift, 모델 배포 변경, checkpoint 불일치, 불완전한 로그의 오판 등이 있습니다.

플랫폼은 이를 명시적 시스템으로 모델링하고 typed contract, 안정적인 ownership, 영속 identity, 증거를 가진 effect, fail-closed 복구 의미론을 사용합니다.

<!-- readme-section:capabilities -->

## 핵심 기능

- 재귀 아키텍처 — 명시적 ownership, 좁은 public API, typed port, composition-time provider binding.
- 실험 인프라 — Study, Run, Branch, Task, Variant, Workload, Checkpoint, Resume, 재현성 identity.
- Agent runtime — Participant, Capability, Action, Memory, Workflow, Execution 경계와 숨은 global lookup 제거.
- 모델 인프라 — catalog, revision, qualification, serving identity, request envelope, prompt binding.
- 환경 인프라 — specification, lifecycle, readiness, observation, effect, snapshot, recovery.
- 프로세스/서버 runtime — supervision, session, toolchain, remote execution, lifecycle control, journal.
- 영속 데이터/Artifact — checksum 상태, WAL recovery, lineage, retention, content-addressed evidence.
- 신뢰성 — failure classification, effect certainty, reconciliation, replay, incident, fail-closed recovery.
- 관측성 — 구조화 log, event, metric, trace, diagnostic, projection, health signal.
- 거버넌스 — architecture, dependency, algorithm, concurrency, performance, forensic, release, no-degradation gate.

<!-- readme-section:architecture -->

## 아키텍처

Composition, Execution, Observation은 서로 분리된 authority plane입니다.

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

Runtime은 global service locator에서 provider를 찾지 않습니다. Observability도 두 번째 command bus가 아닙니다. durable state에는 하나의 owner만 있으며, 외부 effect는 reconciliation으로 증명되기 전까지 UNKNOWN입니다.

`research_platform/governance/system_registry/catalog.json`

<!-- readme-section:downstream -->

## 플랫폼과 downstream 프로젝트

이 저장소는 독립적으로 재사용 가능한 플랫폼 패키지입니다. 연구 방법, task suite, 프로젝트별 환경 구성, 실험 행렬, 모델 선택, 배포 inventory, 과학적 해석은 downstream에 속합니다.

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

Downstream 코드는 public platform contract를 사용하고 프로젝트 소유 구현을 제공합니다. 플랫폼이 downstream 프로젝트를 import하여 과학적 의미나 배포 정책을 결정해서는 안 됩니다.

<!-- readme-section:quick-start -->

## 빠른 시작

### 요구 사항

- Python 3.11 이상
- Git
- 컨테이너 워크플로용 Docker / Docker Compose
- 명시적으로 요구하는 Provider에만 추가 외부 runtime 필요

### 개발 설치

```bash
git clone git@github.com:SDFGAEV/noetrium.git
cd noetrium
python -m venv .venv
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
```

### 플랫폼 확인

```bash
research-platform-architecture-gate
research-platform-algorithm --help
research-platform-concurrency --help
research-platform-performance --help
research-platform-manage --help
```

<!-- readme-section:containers -->

## 컨테이너 워크플로

재사용 가능한 Linux image와 Compose 정의는 `deploy/`에서 관리합니다.

```bash
cp deploy/.env.example deploy/.env
docker compose -f deploy/compose.yaml config
docker compose -f deploy/compose.yaml build
docker compose -f deploy/compose.yaml run --rm platform-runtime doctor
```

Deployment 계층은 immutable software와 mutable runtime state를 분리하고 host별 path와 secret을 commit된 composition code에 넣지 않습니다.

### 내장 Minecraft Provider

Minecraft는 first-party 재사용 environment Provider입니다. Task suite와 과학적 composition은 downstream에 둡니다.

```bash
docker compose -f deploy/compose.yaml -f deploy/compose.minecraft.yaml build platform-runtime
docker compose -f deploy/compose.yaml -f deploy/compose.minecraft.yaml run --rm platform-runtime minecraft-doctor
```

[Minecraft infrastructure](docs/infrastructure/minecraft/README.md)

<!-- readme-section:repository-layout -->

## 리포지토리 구조

| Path | Responsibility |
| --- | --- |
| `research_platform/` | 재사용 가능한 플랫폼 구현과 공개 시스템 경계 |
| `configs/` | 버전 관리 설정 예제와 비밀이 아닌 템플릿 |
| `deploy/` | 컨테이너 이미지, Compose runtime, deployment bootstrap |
| `docs/` | Architecture, infrastructure, governance, status, history 문서 |
| `scripts/` | 얇은 operator, audit, release, maintenance entry point |
| `tests/` | 계층형 regression / contract tests |
| `research_platform/environment/minecraft/` | 재사용 가능한 Minecraft environment provider |
| `LICENSE` / `NOTICE` / `THIRD_PARTY_NOTICES.md` | Apache-2.0 및 서드파티 라이선스 고지 |

`research_platform/` is the reusable package boundary; project-specific code stays downstream.

<!-- readme-section:testing -->

## 테스트와 검증

평가 중인 exact revision에 대해 regression suite와 governance gate를 실행합니다.

```bash
python -m pytest -q
python scripts/architecture_gate.py
python scripts/public_contract_audit.py
python scripts/no_degradation_audit.py
python scripts/check_readme_i18n.py
```

과거의 green result는 현재 tree를 증명하지 않습니다. 게시하거나 배포할 exact revision에 대해 필요한 gate를 다시 실행해야 합니다.

저장소는 계층형 test taxonomy를 사용하여 모든 테스트를 명시적 contract level에 배치하고 release evidence가 실제 검증 범위를 증명하게 합니다. See `tests/TEST_SYSTEM.json`.

<!-- readme-section:principles -->

## 설계 원칙

1. durable state마다 owner는 하나만 둔다.
2. Execution 전에 composition한다.
3. Runtime port를 좁게 유지한다.
4. 외부 effect는 evidence를 가져야 한다.
5. Recovery는 identity-aware여야 한다.
6. silent degradation을 허용하지 않는다.
7. Observation은 authority가 아니다.
8. 성능 변경은 의미를 보존한다.
9. 구현 변경과 문서 변경을 함께 한다.
10. 프로젝트 고유 의미는 downstream에 둔다.

<!-- readme-section:extending -->

## 플랫폼 확장

가장 작은 owner boundary에서 기능을 추가합니다. 공개 contract가 이미 있으면 새 provider를 우선하고, 능력 자체가 새로울 때만 contract를 추가합니다.

```text
<system>/
├── api/          public contracts and identities
├── runtime/      lifecycle and execution semantics
├── providers/    replaceable adapters owned by the system
└── composition/  provider-to-port binding
```

관련 없는 algorithm, provider discovery, 외부 effect를 하나의 범용 wrapper 뒤에 숨기지 마십시오.

<!-- readme-section:documentation -->

## 문서

documentation index에서 시작하십시오.

### 핵심 문서

- [Documentation index](docs/INDEX.md)
- [Platform architecture](docs/architecture/PLATFORM_ARCHITECTURE.md)
- [Detailed system map](docs/architecture/VNEXT_DETAILED_SYSTEM_MAP.md)
- [Architecture migration contract](docs/architecture/FINAL_ARCHITECTURE_MIGRATION_CONTRACT.md)
- [Infrastructure documentation](docs/infrastructure/README.md)
- [Governance documentation](docs/governance/README.md)
- [Current status](docs/status/README.md)
- [Engineering history](docs/history/README.md)

Architecture 문서는 재사용 가능한 ownership과 contract를 정의하고, status 문서는 현재 개발 tree를 설명하며, history는 작성 당시 상태의 증거를 보존합니다.

<!-- readme-section:security -->

## 보안과 설정

- password, private key, access token, runtime secret, 로컬 credential을 commit하지 않는다.
- host별 path와 secret은 ignore된 local profile 또는 environment-bound store에 둔다.
- remote automation은 key/agent 기반 무인 인증을 우선한다.
- 외부 effect command는 typed, bounded, journaled이며 operation identity에 귀속되어야 한다.
- logs와 evidence는 민감한 운영 데이터를 포함할 수 있다고 간주한다.

<!-- readme-section:contributing -->

## 기여

변경은 ownership boundary 기준으로 리뷰 가능해야 하며 이를 증명하는 tests와 documentation을 포함해야 합니다.

### Pull Request 전

```bash
python -m pytest -q
python scripts/architecture_gate.py
python scripts/check_readme_i18n.py
```

- system ownership과 public-contract boundary 유지
- focused regression coverage 추가 또는 갱신
- 같은 change set에서 owner 문서 갱신
- 같은 commit에 무관한 refactor를 섞지 않기
- 불확실한 외부 effect에서 fail-closed 유지
- 의도적인 semantic/compatibility 변경 명시

[Documentation Change Policy](docs/governance/DOCUMENTATION_CHANGE_POLICY.md)

<!-- readme-section:license -->

## 라이선스

Noetrium은 Apache License 2.0을 사용합니다. 법적 권위가 있는 본문은 루트 LICENSE 파일입니다.

서드파티 구성요소는 각자의 라이선스를 따릅니다. THIRD_PARTY_NOTICES.md를 참고하십시오. 독립 배포되는 모델 가중치, 데이터셋, benchmark 자산에는 별도 조건이 있을 수 있습니다.

[`LICENSE`](LICENSE) · [`NOTICE`](NOTICE) · [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)

<!-- readme-section:status -->

## 개발 상태

플랫폼은 아키텍처와 runtime을 계속 개발 중입니다.

프로덕션, 공개, 과학적 주장에서는 오래된 green result에 의존하지 말고 관련 gate를 다시 실행한 뒤 exact source revision에 바인딩된 release evidence를 확인하십시오.

역사적 변경 사항은 의도적으로 이 README에 넣지 않습니다. 불변 engineering record는 `docs/history/`를 사용하십시오.

현재 개발 기준 정보는 `docs/status/CURRENT_DEVELOPMENT_BASELINE.md` 입니다. 릴리스 및 연구 주장은 평가 중인 정확한 리비전에 바인딩된 증거를 사용해야 합니다.

`docs/status/` · `docs/history/`
