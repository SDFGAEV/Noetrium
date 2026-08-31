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
  <strong>Deutsch</strong> ·
  <a href="README.ru.md">Русский</a>
</p>
<!-- readme-nav:end -->



<!-- readme-locale:de -->

<!-- readme-source-sha256:9dd7f68d71e7c6bfc9c059ec68315c5e86dc1ccac0a179645d1e0879c40c283f -->



**Vertragsgetriebene Infrastruktur für reproduzierbare KI-Agenten-Forschung.**



[![Python](https://img.shields.io/badge/Python-%3E%3D3.11-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Version](https://img.shields.io/badge/version-0.43.1-blue)](pyproject.toml)
[![Architecture](https://img.shields.io/badge/architecture-contract--driven-6f42c1)](docs/architecture/PLATFORM_ARCHITECTURE.md)
[![License](https://img.shields.io/badge/license-Apache--2.0-green)](LICENSE)



<!-- readme-section:overview -->

## Überblick

Noetrium ist eine projektunabhängige Plattform zum Bauen, Ausführen, Wiederherstellen, Beobachten, Optimieren und Auditieren langlebiger KI-Agentensysteme und Forschungsworkloads.

Wiederverwendbare Infrastruktur bleibt in der Plattform; paperspezifische wissenschaftliche Semantik, Benchmarks, Experimentmatrizen und Deployment-Policy bleiben in Downstream-Projekten.

<!-- readme-section:why -->

## Warum diese Plattform?

Langlebige Agentensysteme haben mehr Fehlermodi als normale Skripte: Prozessabstürze, ungewisse externe Effects, Environment Drift, geänderte Model Deployments, inkompatible Checkpoints und partielle Logs, die fälschlich als gültige Evidenz gelten können.

Die Plattform modelliert diese Probleme als explizite Systeme mit typed contracts, stabilem ownership, dauerhaften identities, evidenztragenden effects und fail-closed recovery semantics.

<!-- readme-section:capabilities -->

## Kernfunktionen

- Rekursive Architektur — explizites ownership, schmale öffentliche APIs, typed ports und composition-time provider binding.
- Experiment-Infrastruktur — Study, Run, Branch, Task, Variant, Workload, Checkpoint, Resume und Reproduzierbarkeits-identities.
- Agent Runtime — Grenzen für Participant, Capability, Action, Memory, Workflow und Execution ohne versteckten global lookup.
- Modell-Infrastruktur — catalog, revision, qualification, serving identity, request envelope und prompt binding.
- Environment-Infrastruktur — specification, lifecycle, readiness, observation, effects, snapshots und recovery.
- Prozess/Server-Runtime — supervision, sessions, toolchains, Remote Execution, lifecycle control und journals.
- Dauerhafte Daten/Artifacts — checksummed state, WAL recovery, lineage, retention und content-addressed evidence.
- Reliability — failure classification, effect certainty, reconciliation, replay, incidents und fail-closed recovery.
- Observability — strukturierte Logs, events, metrics, traces, diagnostics, projections und health signals.
- Governance — Gates für architecture, dependency, algorithm, concurrency, performance, forensic, release und no-degradation.

<!-- readme-section:architecture -->

## Architektur

Composition, Execution und Observation sind getrennte Authority-Planes.

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

Runtime entdeckt Providers nicht über einen globalen service locator. Observability ist kein zweiter command bus. Jeder durable state hat genau einen owner, und externe effects bleiben UNKNOWN, bis reconciliation ihren Zustand beweist.

`research_platform/governance/system_registry/catalog.json`

<!-- readme-section:downstream -->

## Plattform und Downstream-Projekte

Dieses Repository ist ein unabhängig nutzbares Plattformpaket. Forschungsmethoden, task suites, projektspezifische Environment-Komposition, Experimentmatrizen, Model-Auswahl, Deployment-Inventare und wissenschaftliche Interpretation gehören downstream.

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

Downstream-Code konsumiert öffentliche Platform-Contracts und liefert eigene Implementierungen; die Plattform darf kein Downstream-Projekt importieren, um wissenschaftliche Bedeutung oder Deployment-Policy zu bestimmen.

<!-- readme-section:quick-start -->

## Schnellstart

### Anforderungen

- Python 3.11 oder neuer
- Git
- Docker / Docker Compose für Container-Workflows
- Optionale externe Runtimes nur für Providers, die sie ausdrücklich benötigen

### Installation für Entwicklung

```bash
git clone git@github.com:SDFGAEV/noetrium.git
cd noetrium
python -m venv .venv
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
```

### Plattform prüfen

```bash
research-platform-architecture-gate
research-platform-algorithm --help
research-platform-concurrency --help
research-platform-performance --help
research-platform-manage --help
```

<!-- readme-section:containers -->

## Container-Workflow

Ein wiederverwendbares Linux-Image und eine Compose-Definition werden unter `deploy/` gepflegt.

```bash
cp deploy/.env.example deploy/.env
docker compose -f deploy/compose.yaml config
docker compose -f deploy/compose.yaml build
docker compose -f deploy/compose.yaml run --rm platform-runtime doctor
```

Die Deployment-Schicht trennt immutable software von mutable runtime state; host-spezifische paths und secrets bleiben außerhalb des versionierten composition code.

### Mitgelieferter Minecraft Provider

Minecraft ist ein wiederverwendbarer first-party Environment Provider. Task suites und wissenschaftliche Composition bleiben downstream.

```bash
docker compose -f deploy/compose.yaml -f deploy/compose.minecraft.yaml build platform-runtime
docker compose -f deploy/compose.yaml -f deploy/compose.minecraft.yaml run --rm platform-runtime minecraft-doctor
```

[Minecraft infrastructure](docs/infrastructure/minecraft/README.md)

<!-- readme-section:repository-layout -->

## Repository-Struktur

| Path | Responsibility |
| --- | --- |
| `research_platform/` | Wiederverwendbare Plattformimplementierung und öffentliche Systemgrenzen |
| `configs/` | Versionierte Konfigurationsbeispiele und secret-freie Templates |
| `deploy/` | Container-Image, Compose Runtime und Deployment-Bootstrap |
| `docs/` | Dokumentation für architecture, infrastructure, governance, status und history |
| `scripts/` | Dünne operator-, audit-, release- und maintenance-Einstiegspunkte |
| `tests/` | Hierarchische Regression- und Contract-Tests |
| `research_platform/environment/minecraft/` | Wiederverwendbarer Minecraft Environment Provider |
| `LICENSE` / `NOTICE` / `THIRD_PARTY_NOTICES.md` | Apache-2.0- und Drittanbieter-Lizenzhinweise |

`research_platform/` is the reusable package boundary; project-specific code stays downstream.

<!-- readme-section:testing -->

## Tests und Verifikation

Führen Sie Regression und Governance-Gates für die bewertete exact revision aus.

```bash
python -m pytest -q
python scripts/architecture_gate.py
python scripts/public_contract_audit.py
python scripts/no_degradation_audit.py
python scripts/check_readme_i18n.py
```

Ein historisch grünes Ergebnis beweist nicht den aktuellen Tree. Führen Sie die relevanten Gates für die exact revision erneut aus, die veröffentlicht oder deployed werden soll.

Das Repository verwendet eine hierarchische Test-Taxonomie, damit jeder Test einem expliziten contract level zugeordnet ist und release evidence den tatsächlich geprüften Umfang nachweisen kann. See `tests/TEST_SYSTEM.json`.

<!-- readme-section:principles -->

## Designprinzipien

1. Ein owner pro durable state.
2. Composition vor execution.
3. Schmale runtime ports.
4. Externe effects tragen evidence.
5. Recovery ist identity-aware.
6. Keine silent degradation.
7. Observation ist keine authority.
8. Performance-Änderungen erhalten Semantik.
9. Dokumentation folgt der Implementierung.
10. Projekte bleiben downstream.

<!-- readme-section:extending -->

## Plattform erweitern

Fügen Sie Fähigkeiten an der kleinsten owning boundary hinzu. Wenn der öffentliche Contract bereits existiert, bevorzugen Sie einen neuen provider; ein neuer Contract ist nur nötig, wenn die Fähigkeit selbst neu ist.

```text
<system>/
├── api/          public contracts and identities
├── runtime/      lifecycle and execution semantics
├── providers/    replaceable adapters owned by the system
└── composition/  provider-to-port binding
```

Vermeiden Sie generische Wrapper, die unabhängige Algorithmen, provider discovery oder externe effects hinter einer einzigen Schnittstelle verstecken.

<!-- readme-section:documentation -->

## Dokumentation

Beginnen Sie mit dem Dokumentationsindex.

### Wichtige Referenzen

- [Documentation index](docs/INDEX.md)
- [Platform architecture](docs/architecture/PLATFORM_ARCHITECTURE.md)
- [Detailed system map](docs/architecture/VNEXT_DETAILED_SYSTEM_MAP.md)
- [Architecture migration contract](docs/architecture/FINAL_ARCHITECTURE_MIGRATION_CONTRACT.md)
- [Infrastructure documentation](docs/infrastructure/README.md)
- [Governance documentation](docs/governance/README.md)
- [Current status](docs/status/README.md)
- [Engineering history](docs/history/README.md)

Architecture-Dokumente definieren wiederverwendbares ownership und contracts; status-Dokumente beschreiben den aktuellen Development Tree; history bewahrt Evidenz des Zustands zum Zeitpunkt der Erstellung.

<!-- readme-section:security -->

## Sicherheit und Konfiguration

- Nie Passwörter, private Schlüssel, Tokens, runtime secrets oder lokale Credentials committen.
- Host-spezifische paths und secrets in ignorierten lokalen profiles oder environment-bound stores halten.
- Für Remote-Automation key/agent-basierte unbeaufsichtigte Authentifizierung bevorzugen.
- External-effect commands müssen typed, bounded, journaled und einer operation identity zuordenbar sein.
- Logs und evidence als potenziell sensible Betriebsdaten behandeln.

<!-- readme-section:contributing -->

## Mitwirken

Änderungen sollen entlang der ownership boundary reviewbar sein und die nötigen Tests und Dokumentation enthalten.

### Vor dem Öffnen eines Pull Requests

```bash
python -m pytest -q
python scripts/architecture_gate.py
python scripts/check_readme_i18n.py
```

- system ownership und public-contract boundaries bewahren
- fokussierte Regression-Coverage hinzufügen oder aktualisieren
- Owner-Dokumentation im selben change set aktualisieren
- keine unabhängigen Refactors im selben Commit
- fail-closed für unsichere externe effects bewahren
- beabsichtigte Semantik- oder Kompatibilitätsänderungen explizit dokumentieren

[Documentation Change Policy](docs/governance/DOCUMENTATION_CHANGE_POLICY.md)

<!-- readme-section:license -->

## Lizenz

Noetrium steht unter der Apache License 2.0. Rechtlich maßgeblich ist die LICENSE-Datei im Repository-Root.

Drittanbieter-Komponenten unterliegen weiterhin ihren eigenen Lizenzen; siehe THIRD_PARTY_NOTICES.md. Separat verteilte Model Weights, Datasets oder Benchmark-Assets können eigene Bedingungen angeben.

[`LICENSE`](LICENSE) · [`NOTICE`](NOTICE) · [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)

<!-- readme-section:status -->

## Entwicklungsstatus

Die Plattform befindet sich weiterhin in aktiver Architektur- und Runtime-Entwicklung.

Für Produktion, Veröffentlichung oder wissenschaftliche Aussagen müssen die relevanten Gates erneut ausgeführt und release evidence der exact source revision geprüft werden; ein altes grünes Ergebnis reicht nicht aus.

Historische Änderungen werden bewusst nicht in dieses README aufgenommen; unveränderliche Engineering-Aufzeichnungen liegen unter `docs/history/`.

Die aktuelle Entwicklungswahrheit steht in `docs/status/CURRENT_DEVELOPMENT_BASELINE.md`; Release- und Forschungsaussagen müssen an Evidenz der exakt bewerteten Revision gebunden sein.

`docs/status/` · `docs/history/`
