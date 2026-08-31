# Noetrium: Reproducible Research Infrastructure for AI Agents



<!-- readme-nav:start -->
<p align="center">
  <a href="README.md">English</a> ·
  <a href="README.zh-CN.md">简体中文</a> ·
  <a href="README.zh-TW.md">繁體中文</a> ·
  <a href="README.ja.md">日本語</a> ·
  <a href="README.ko.md">한국어</a> ·
  <strong>Español</strong> ·
  <a href="README.pt-BR.md">Português (Brasil)</a> ·
  <a href="README.fr.md">Français</a> ·
  <a href="README.de.md">Deutsch</a> ·
  <a href="README.ru.md">Русский</a>
</p>
<!-- readme-nav:end -->



<!-- readme-locale:es -->

<!-- readme-source-sha256:9dd7f68d71e7c6bfc9c059ec68315c5e86dc1ccac0a179645d1e0879c40c283f -->



**Infraestructura basada en contratos para investigación reproducible con agentes de IA.**



[![Python](https://img.shields.io/badge/Python-%3E%3D3.11-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Version](https://img.shields.io/badge/version-0.43.1-blue)](pyproject.toml)
[![Architecture](https://img.shields.io/badge/architecture-contract--driven-6f42c1)](docs/architecture/PLATFORM_ARCHITECTURE.md)
[![License](https://img.shields.io/badge/license-Apache--2.0-green)](LICENSE)



<!-- readme-section:overview -->

## Descripción general

Noetrium es una plataforma independiente del proyecto para construir, ejecutar, recuperar, observar, optimizar y auditar sistemas de agentes de IA de larga duración y cargas de investigación.

La infraestructura reutilizable permanece en la plataforma; la semántica científica de cada artículo, los benchmarks, las matrices experimentales y la política de despliegue permanecen en los proyectos downstream.

<!-- readme-section:why -->

## ¿Por qué esta plataforma?

Los sistemas de agentes de larga duración fallan de más formas que un script normal: procesos que terminan, efectos externos inciertos, deriva del entorno, cambios de despliegue de modelos, checkpoints incompatibles y logs parciales que pueden confundirse con evidencia válida.

La plataforma modela estos problemas como sistemas explícitos con typed contracts, ownership estable, identidades durables, efectos con evidencia y recuperación fail-closed.

<!-- readme-section:capabilities -->

## Capacidades principales

- Arquitectura recursiva — ownership explícito, API pública estrecha, typed ports y provider binding en composición.
- Infraestructura experimental — Study, Run, Branch, Task, Variant, Workload, Checkpoint, Resume e identidades de reproducibilidad.
- Runtime de agentes — límites de Participant, Capability, Action, Memory, Workflow y Execution sin lookup global oculto.
- Infraestructura de modelos — catalog, revision, qualification, serving identity, request envelope y prompt binding.
- Infraestructura de entorno — specification, lifecycle, readiness, observation, effects, snapshots y recovery.
- Runtime de procesos/servidores — supervision, sessions, toolchains, ejecución remota, control de lifecycle y journals.
- Datos/Artifacts durables — estado con checksum, recuperación WAL, lineage, retention y evidencia content-addressed.
- Fiabilidad — clasificación de fallos, effect certainty, reconciliation, replay, incidents y recuperación fail-closed.
- Observabilidad — logs estructurados, events, metrics, traces, diagnostics, projections y señales de salud.
- Gobernanza — gates de architecture, dependency, algorithm, concurrency, performance, forensic, release y no-degradation.

<!-- readme-section:architecture -->

## Arquitectura

Composition, Execution y Observation son planos de autoridad separados.

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

El runtime no descubre providers mediante un service locator global. Observability no es un segundo command bus. Cada durable state tiene un solo owner y los efectos externos permanecen UNKNOWN hasta que reconciliation demuestre lo contrario.

`research_platform/governance/system_registry/catalog.json`

<!-- readme-section:downstream -->

## Plataforma y proyectos downstream

Este repositorio es un paquete de plataforma reutilizable e independiente. Métodos de investigación, task suites, composición de entorno específica, matrices experimentales, selección de modelos, inventarios de despliegue e interpretación científica pertenecen downstream.

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

El código downstream consume contratos públicos de la plataforma y aporta implementaciones propias; la plataforma no debe importar un proyecto downstream para decidir significado científico o política de despliegue.

<!-- readme-section:quick-start -->

## Inicio rápido

### Requisitos

- Python 3.11 o superior
- Git
- Docker / Docker Compose para flujos de contenedores
- Runtimes externos opcionales solo para Providers que los requieran explícitamente

### Instalación para desarrollo

```bash
git clone git@github.com:SDFGAEV/noetrium.git
cd noetrium
python -m venv .venv
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
```

### Inspeccionar la plataforma

```bash
research-platform-architecture-gate
research-platform-algorithm --help
research-platform-concurrency --help
research-platform-performance --help
research-platform-manage --help
```

<!-- readme-section:containers -->

## Flujo de contenedores

La imagen Linux reutilizable y la definición Compose se mantienen en `deploy/`.

```bash
cp deploy/.env.example deploy/.env
docker compose -f deploy/compose.yaml config
docker compose -f deploy/compose.yaml build
docker compose -f deploy/compose.yaml run --rm platform-runtime doctor
```

La capa de deployment separa software inmutable de runtime state mutable; paths del host y secrets quedan fuera del composition code versionado.

### Provider Minecraft incluido

Minecraft es un Provider de entorno reutilizable de primera parte. Task suites y composición científica permanecen downstream.

```bash
docker compose -f deploy/compose.yaml -f deploy/compose.minecraft.yaml build platform-runtime
docker compose -f deploy/compose.yaml -f deploy/compose.minecraft.yaml run --rm platform-runtime minecraft-doctor
```

[Minecraft infrastructure](docs/infrastructure/minecraft/README.md)

<!-- readme-section:repository-layout -->

## Estructura del repositorio

| Path | Responsibility |
| --- | --- |
| `research_platform/` | Implementación reutilizable y límites públicos del sistema |
| `configs/` | Ejemplos de configuración versionados y plantillas sin secretos |
| `deploy/` | Imagen de contenedor, runtime Compose y bootstrap de despliegue |
| `docs/` | Documentación de architecture, infrastructure, governance, status e history |
| `scripts/` | Entradas ligeras de operator, audit, release y mantenimiento |
| `tests/` | Pruebas jerárquicas de regresión y contratos |
| `research_platform/environment/minecraft/` | Provider reutilizable de entorno Minecraft |
| `LICENSE` / `NOTICE` / `THIRD_PARTY_NOTICES.md` | Avisos Apache-2.0 y licencias de terceros |

`research_platform/` is the reusable package boundary; project-specific code stays downstream.

<!-- readme-section:testing -->

## Pruebas y verificación

Ejecuta la regresión y los governance gates sobre la exact revision evaluada.

```bash
python -m pytest -q
python scripts/architecture_gate.py
python scripts/public_contract_audit.py
python scripts/no_degradation_audit.py
python scripts/check_readme_i18n.py
```

Un resultado verde histórico no demuestra el árbol actual. Vuelve a ejecutar los gates relevantes para la exact revision que quieras publicar o desplegar.

El repositorio usa una taxonomía jerárquica de pruebas para asignar cada test a un contract level explícito y permitir que release evidence demuestre qué se ejercitó realmente. See `tests/TEST_SYSTEM.json`.

<!-- readme-section:principles -->

## Principios de diseño

1. Un owner por durable state.
2. Composition antes de execution.
3. Runtime ports estrechos.
4. Los efectos externos llevan evidence.
5. Recovery es identity-aware.
6. Sin silent degradation.
7. Observation no es authority.
8. Los cambios de rendimiento conservan semántica.
9. La documentación cambia con la implementación.
10. Los proyectos permanecen downstream.

<!-- readme-section:extending -->

## Extender la plataforma

Añade capacidades en el límite del owner más pequeño. Si el contrato público ya existe, prefiere un nuevo provider; crea un nuevo contract solo cuando la capacidad sea realmente nueva.

```text
<system>/
├── api/          public contracts and identities
├── runtime/      lifecycle and execution semantics
├── providers/    replaceable adapters owned by the system
└── composition/  provider-to-port binding
```

Evita wrappers genéricos que oculten algoritmos no relacionados, provider discovery o efectos externos tras una sola interfaz.

<!-- readme-section:documentation -->

## Documentación

Empieza por el índice de documentación.

### Referencias clave

- [Documentation index](docs/INDEX.md)
- [Platform architecture](docs/architecture/PLATFORM_ARCHITECTURE.md)
- [Detailed system map](docs/architecture/VNEXT_DETAILED_SYSTEM_MAP.md)
- [Architecture migration contract](docs/architecture/FINAL_ARCHITECTURE_MIGRATION_CONTRACT.md)
- [Infrastructure documentation](docs/infrastructure/README.md)
- [Governance documentation](docs/governance/README.md)
- [Current status](docs/status/README.md)
- [Engineering history](docs/history/README.md)

Los documentos de architecture definen ownership y contracts reutilizables; los documentos de status describen el árbol actual; history conserva evidencia del estado existente cuando fue escrito.

<!-- readme-section:security -->

## Seguridad y configuración

- Nunca hagas commit de contraseñas, claves privadas, tokens, runtime secrets o credenciales locales.
- Mantén paths específicos del host y secrets en perfiles locales ignorados o stores ligados al entorno.
- Prefiere autenticación no atendida basada en key/agent para automatización remota.
- Los comandos con efectos externos deben ser typed, bounded, journaled y atribuibles a una operation identity.
- Trata logs y evidence como datos operativos potencialmente sensibles.

<!-- readme-section:contributing -->

## Contribuir

Los cambios deben poder revisarse por ownership boundary e incluir tests y documentación suficientes para demostrarlos.

### Antes de abrir un Pull Request

```bash
python -m pytest -q
python scripts/architecture_gate.py
python scripts/check_readme_i18n.py
```

- preservar system ownership y public-contract boundaries
- añadir o actualizar cobertura de regresión enfocada
- actualizar la documentación del owner en el mismo change set
- evitar refactors no relacionados en el mismo commit
- preservar fail-closed para efectos externos inciertos
- documentar explícitamente cambios intencionales de semántica o compatibilidad

[Documentation Change Policy](docs/governance/DOCUMENTATION_CHANGE_POLICY.md)

<!-- readme-section:license -->

## Licencia

Noetrium se distribuye bajo Apache License 2.0. El texto legal autoritativo es el archivo LICENSE en la raíz.

Los componentes de terceros conservan sus propias licencias; consulta THIRD_PARTY_NOTICES.md. Pesos de modelos, datasets o assets de benchmark distribuidos de forma independiente pueden declarar términos separados.

[`LICENSE`](LICENSE) · [`NOTICE`](NOTICE) · [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)

<!-- readme-section:status -->

## Estado de desarrollo

La plataforma continúa en desarrollo activo de arquitectura y runtime.

Para producción, publicación o afirmaciones científicas, vuelve a ejecutar los gates pertinentes y revisa release evidence vinculada a la exact source revision, en lugar de confiar en un resultado verde antiguo.

Los cambios históricos se mantienen intencionadamente fuera de este README; usa `docs/history/` para los registros de ingeniería inmutables.

La fuente vigente del estado de desarrollo es `docs/status/CURRENT_DEVELOPMENT_BASELINE.md`; las afirmaciones de publicación o investigación deben vincularse a evidencia de la revisión exacta evaluada.

`docs/status/` · `docs/history/`
