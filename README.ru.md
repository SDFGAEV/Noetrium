# Noetrium: Reproducible Research Infrastructure for AI Agents



<!-- readme-nav:start -->
<p align="center">
  <a href="README.md">English</a> ·
  <a href="README.zh-CN.md">简体中文</a> ·
  <a href="README.zh-TW.md">繁體中文</a> ·
  <a href="README.ja.md">日本語</a> ·
  <a href="README.ko.md">한국어</a> ·
  <a href="README.es.md">Español</a> ·
  <a href="README.pt-BR.md">Português (Brasil)</a> ·
  <a href="README.fr.md">Français</a> ·
  <a href="README.de.md">Deutsch</a> ·
  <strong>Русский</strong>
</p>
<!-- readme-nav:end -->



<!-- readme-locale:ru -->

<!-- readme-source-sha256:9dd7f68d71e7c6bfc9c059ec68315c5e86dc1ccac0a179645d1e0879c40c283f -->



**Контрактно-ориентированная инфраструктура для воспроизводимых исследований ИИ-агентов.**



[![Python](https://img.shields.io/badge/Python-%3E%3D3.11-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Version](https://img.shields.io/badge/version-0.43.1-blue)](pyproject.toml)
[![Architecture](https://img.shields.io/badge/architecture-contract--driven-6f42c1)](docs/architecture/PLATFORM_ARCHITECTURE.md)
[![License](https://img.shields.io/badge/license-Apache--2.0-green)](LICENSE)



<!-- readme-section:overview -->

## Обзор

Noetrium — независимая от конкретного проекта платформа для построения, запуска, восстановления, наблюдения, оптимизации и аудита долгоживущих систем ИИ-агентов и исследовательских нагрузок.

Повторно используемая инфраструктура остаётся в платформе; научная семантика конкретной статьи, benchmarks, экспериментальные матрицы и политика deployment остаются в downstream-проектах.

<!-- readme-section:why -->

## Зачем нужна эта платформа?

Долгоживущие Agent-системы имеют больше режимов отказа, чем обычные скрипты: падение процессов, неопределённость внешних effects, drift окружения, изменение model deployment, несовместимые checkpoints и неполные logs, которые можно ошибочно принять за достоверное evidence.

Платформа моделирует эти проблемы как явные системы с typed contracts, стабильным ownership, долговечными identities, effects с evidence и fail-closed семантикой восстановления.

<!-- readme-section:capabilities -->

## Основные возможности

- Рекурсивная архитектура — явный ownership, узкие публичные API, typed ports и composition-time provider binding.
- Экспериментальная инфраструктура — Study, Run, Branch, Task, Variant, Workload, Checkpoint, Resume и identities воспроизводимости.
- Agent runtime — границы Participant, Capability, Action, Memory, Workflow и Execution без скрытого global lookup.
- Инфраструктура моделей — catalog, revision, qualification, serving identity, request envelope и prompt binding.
- Инфраструктура окружений — specification, lifecycle, readiness, observation, effects, snapshots и recovery.
- Runtime процессов/серверов — supervision, sessions, toolchains, удалённое выполнение, lifecycle control и journals.
- Долговечные данные/Artifacts — checksummed state, WAL recovery, lineage, retention и content-addressed evidence.
- Надёжность — классификация отказов, effect certainty, reconciliation, replay, incidents и fail-closed recovery.
- Наблюдаемость — структурированные logs, events, metrics, traces, diagnostics, projections и health signals.
- Governance — gates для architecture, dependency, algorithm, concurrency, performance, forensic, release и no-degradation.

<!-- readme-section:architecture -->

## Архитектура

Composition, Execution и Observation являются отдельными authority planes.

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

Runtime не обнаруживает providers через глобальный service locator. Observability не становится вторым command bus. У каждого durable state один owner, а внешние effects остаются UNKNOWN, пока reconciliation не докажет их состояние.

`research_platform/governance/system_registry/catalog.json`

<!-- readme-section:downstream -->

## Платформа и downstream-проекты

Этот репозиторий является независимо используемым пакетом платформы. Методы исследования, task suites, проектная композиция окружения, экспериментальные матрицы, выбор моделей, deployment inventories и научная интерпретация принадлежат downstream-проектам.

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

Downstream-код использует публичные platform contracts и предоставляет собственные реализации; платформа не должна импортировать downstream-проект, чтобы определять научный смысл или deployment policy.

<!-- readme-section:quick-start -->

## Быстрый старт

### Требования

- Python 3.11 или новее
- Git
- Docker / Docker Compose для контейнерных workflow
- Дополнительные внешние runtimes только для Providers, которым они явно нужны

### Установка для разработки

```bash
git clone git@github.com:SDFGAEV/noetrium.git
cd noetrium
python -m venv .venv
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
```

### Проверка платформы

```bash
research-platform-architecture-gate
research-platform-algorithm --help
research-platform-concurrency --help
research-platform-performance --help
research-platform-manage --help
```

<!-- readme-section:containers -->

## Контейнерный workflow

Повторно используемый Linux image и Compose-описание находятся в `deploy/`.

```bash
cp deploy/.env.example deploy/.env
docker compose -f deploy/compose.yaml config
docker compose -f deploy/compose.yaml build
docker compose -f deploy/compose.yaml run --rm platform-runtime doctor
```

Deployment-слой отделяет immutable software от mutable runtime state; host-specific paths и secrets не попадают в versioned composition code.

### Встроенный Minecraft Provider

Minecraft — first-party повторно используемый Environment Provider. Task suites и научная composition остаются downstream.

```bash
docker compose -f deploy/compose.yaml -f deploy/compose.minecraft.yaml build platform-runtime
docker compose -f deploy/compose.yaml -f deploy/compose.minecraft.yaml run --rm platform-runtime minecraft-doctor
```

[Minecraft infrastructure](docs/infrastructure/minecraft/README.md)

<!-- readme-section:repository-layout -->

## Структура репозитория

| Path | Responsibility |
| --- | --- |
| `research_platform/` | Повторно используемая реализация платформы и публичные системные границы |
| `configs/` | Версионируемые примеры конфигурации и шаблоны без секретов |
| `deploy/` | Контейнерный образ, Compose runtime и deployment bootstrap |
| `docs/` | Документация architecture, infrastructure, governance, status и history |
| `scripts/` | Тонкие operator, audit, release и maintenance entry points |
| `tests/` | Иерархические regression и contract tests |
| `research_platform/environment/minecraft/` | Повторно используемый Minecraft environment provider |
| `LICENSE` / `NOTICE` / `THIRD_PARTY_NOTICES.md` | Уведомления Apache-2.0 и лицензии третьих сторон |

`research_platform/` is the reusable package boundary; project-specific code stays downstream.

<!-- readme-section:testing -->

## Тестирование и проверка

Запускайте regression suite и governance gates на оцениваемой exact revision.

```bash
python -m pytest -q
python scripts/architecture_gate.py
python scripts/public_contract_audit.py
python scripts/no_degradation_audit.py
python scripts/check_readme_i18n.py
```

Исторически зелёный результат не доказывает текущее дерево. Повторно запустите необходимые gates для exact revision, которую планируется публиковать или развёртывать.

Репозиторий использует иерархическую test taxonomy, поэтому каждый тест принадлежит явному contract level, а release evidence может доказать фактический объём проверки. See `tests/TEST_SYSTEM.json`.

<!-- readme-section:principles -->

## Принципы проектирования

1. Один owner на каждый durable state.
2. Composition до execution.
3. Узкие runtime ports.
4. Внешние effects несут evidence.
5. Recovery должен быть identity-aware.
6. Никакой silent degradation.
7. Observation не является authority.
8. Изменения performance сохраняют семантику.
9. Документация меняется вместе с реализацией.
10. Проектная специфика остаётся downstream.

<!-- readme-section:extending -->

## Расширение платформы

Добавляйте способность на минимальной owning boundary. Если публичный contract уже существует, предпочтите новый provider; добавляйте новый contract только когда сама способность действительно новая.

```text
<system>/
├── api/          public contracts and identities
├── runtime/      lifecycle and execution semantics
├── providers/    replaceable adapters owned by the system
└── composition/  provider-to-port binding
```

Не используйте универсальные wrappers, скрывающие несвязанные алгоритмы, provider discovery или внешние effects за одним интерфейсом.

<!-- readme-section:documentation -->

## Документация

Начните с индекса документации.

### Основные документы

- [Documentation index](docs/INDEX.md)
- [Platform architecture](docs/architecture/PLATFORM_ARCHITECTURE.md)
- [Detailed system map](docs/architecture/VNEXT_DETAILED_SYSTEM_MAP.md)
- [Architecture migration contract](docs/architecture/FINAL_ARCHITECTURE_MIGRATION_CONTRACT.md)
- [Infrastructure documentation](docs/infrastructure/README.md)
- [Governance documentation](docs/governance/README.md)
- [Current status](docs/status/README.md)
- [Engineering history](docs/history/README.md)

Architecture-документы определяют повторно используемые ownership и contracts; status-документы описывают текущее дерево разработки; history сохраняет evidence состояния на момент записи.

<!-- readme-section:security -->

## Безопасность и конфигурация

- Никогда не коммитьте пароли, private keys, access tokens, runtime secrets или локальные credentials.
- Host-specific paths и secrets храните в игнорируемых local profiles или environment-bound stores.
- Для remote automation предпочитайте unattended authentication на основе key/agent.
- Команды с внешними effects должны быть typed, bounded, journaled и связаны с operation identity.
- Считайте logs и evidence потенциально чувствительными operational data.

<!-- readme-section:contributing -->

## Участие в разработке

Изменения должны быть проверяемы по ownership boundary и включать необходимые tests и documentation.

### Перед открытием Pull Request

```bash
python -m pytest -q
python scripts/architecture_gate.py
python scripts/check_readme_i18n.py
```

- сохранять system ownership и public-contract boundaries
- добавлять или обновлять focused regression coverage
- обновлять документацию owner в том же change set
- не смешивать несвязанные refactors в одном commit
- сохранять fail-closed для неопределённых внешних effects
- явно документировать намеренные semantic или compatibility изменения

[Documentation Change Policy](docs/governance/DOCUMENTATION_CHANGE_POLICY.md)

<!-- readme-section:license -->

## Лицензия

Noetrium распространяется по Apache License 2.0. Юридически авторитетный текст находится в корневом файле LICENSE.

Сторонние компоненты остаются под своими лицензиями; см. THIRD_PARTY_NOTICES.md. Отдельно распространяемые веса моделей, datasets или benchmark assets могут иметь собственные условия.

[`LICENSE`](LICENSE) · [`NOTICE`](NOTICE) · [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)

<!-- readme-section:status -->

## Статус разработки

Платформа продолжает активную разработку архитектуры и runtime.

Для production, публикации или научных утверждений повторно запускайте соответствующие gates и проверяйте release evidence, привязанное к exact source revision, вместо того чтобы полагаться на старый зелёный результат.

Исторические изменения намеренно не включаются в этот README; неизменяемые инженерные записи находятся в `docs/history/`.

Текущее достоверное состояние разработки зафиксировано в `docs/status/CURRENT_DEVELOPMENT_BASELINE.md`; утверждения о релизе или исследованиях должны опираться на свидетельства, привязанные к точной проверяемой ревизии.

`docs/status/` · `docs/history/`
