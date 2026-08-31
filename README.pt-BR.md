# Noetrium: Reproducible Research Infrastructure for AI Agents



<!-- readme-nav:start -->
<p align="center">
  <a href="README.md">English</a> ·
  <a href="README.zh-CN.md">简体中文</a> ·
  <a href="README.zh-TW.md">繁體中文</a> ·
  <a href="README.ja.md">日本語</a> ·
  <a href="README.ko.md">한국어</a> ·
  <a href="README.es.md">Español</a> ·
  <strong>Português (Brasil)</strong> ·
  <a href="README.fr.md">Français</a> ·
  <a href="README.de.md">Deutsch</a> ·
  <a href="README.ru.md">Русский</a>
</p>
<!-- readme-nav:end -->



<!-- readme-locale:pt-BR -->

<!-- readme-source-sha256:9dd7f68d71e7c6bfc9c059ec68315c5e86dc1ccac0a179645d1e0879c40c283f -->



**Infraestrutura orientada a contratos para pesquisa reproduzível com agentes de IA.**



[![Python](https://img.shields.io/badge/Python-%3E%3D3.11-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Version](https://img.shields.io/badge/version-0.43.1-blue)](pyproject.toml)
[![Architecture](https://img.shields.io/badge/architecture-contract--driven-6f42c1)](docs/architecture/PLATFORM_ARCHITECTURE.md)
[![License](https://img.shields.io/badge/license-Apache--2.0-green)](LICENSE)



<!-- readme-section:overview -->

## Visão geral

Noetrium é uma plataforma independente de projeto para construir, executar, recuperar, observar, otimizar e auditar sistemas de agentes de IA de longa duração e workloads de pesquisa.

A infraestrutura reutilizável permanece na plataforma; a semântica científica específica de artigos, benchmarks, matrizes experimentais e políticas de deployment permanecem nos projetos downstream.

<!-- readme-section:why -->

## Por que esta plataforma?

Sistemas de agentes de longa duração falham de mais formas que scripts comuns: processos encerram, efeitos externos ficam incertos, ambientes sofrem drift, deployments de modelos mudam, checkpoints tornam-se incompatíveis e logs parciais podem ser confundidos com evidência válida.

A plataforma modela essas questões como sistemas explícitos com typed contracts, ownership estável, identidades duráveis, effects com evidência e recuperação fail-closed.

<!-- readme-section:capabilities -->

## Principais capacidades

- Arquitetura recursiva — ownership explícito, APIs públicas estreitas, typed ports e provider binding em composition-time.
- Infraestrutura experimental — Study, Run, Branch, Task, Variant, Workload, Checkpoint, Resume e identidades de reprodutibilidade.
- Runtime de agentes — limites de Participant, Capability, Action, Memory, Workflow e Execution sem lookup global oculto.
- Infraestrutura de modelos — catalog, revision, qualification, serving identity, request envelope e prompt binding.
- Infraestrutura de ambiente — specification, lifecycle, readiness, observation, effects, snapshots e recovery.
- Runtime de processos/servidores — supervision, sessions, toolchains, execução remota, controle de lifecycle e journals.
- Dados/Artifacts duráveis — estado com checksum, recuperação WAL, lineage, retention e evidência content-addressed.
- Confiabilidade — classificação de falhas, effect certainty, reconciliation, replay, incidents e recuperação fail-closed.
- Observabilidade — logs estruturados, events, metrics, traces, diagnostics, projections e sinais de saúde.
- Governança — gates de architecture, dependency, algorithm, concurrency, performance, forensic, release e no-degradation.

<!-- readme-section:architecture -->

## Arquitetura

Composition, Execution e Observation são planos de autoridade separados.

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

O runtime não descobre providers por um service locator global. Observability não é um segundo command bus. Cada durable state possui um único owner e effects externos permanecem UNKNOWN até que reconciliation prove seu resultado.

`research_platform/governance/system_registry/catalog.json`

<!-- readme-section:downstream -->

## Plataforma e projetos downstream

Este repositório é um pacote de plataforma reutilizável e independente. Métodos de pesquisa, task suites, composição de ambiente específica, matrizes experimentais, escolhas de modelos, inventários de deployment e interpretação científica pertencem aos projetos downstream.

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

Código downstream consome contracts públicos da plataforma e fornece implementações próprias; a plataforma não deve importar um projeto downstream para decidir significado científico ou política de deployment.

<!-- readme-section:quick-start -->

## Início rápido

### Requisitos

- Python 3.11 ou superior
- Git
- Docker / Docker Compose para fluxos em containers
- Runtimes externos opcionais apenas para Providers que explicitamente os exigem

### Instalação para desenvolvimento

```bash
git clone git@github.com:SDFGAEV/noetrium.git
cd noetrium
python -m venv .venv
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
```

### Inspecionar a plataforma

```bash
research-platform-architecture-gate
research-platform-algorithm --help
research-platform-concurrency --help
research-platform-performance --help
research-platform-manage --help
```

<!-- readme-section:containers -->

## Fluxo de containers

A imagem Linux reutilizável e a definição Compose ficam em `deploy/`.

```bash
cp deploy/.env.example deploy/.env
docker compose -f deploy/compose.yaml config
docker compose -f deploy/compose.yaml build
docker compose -f deploy/compose.yaml run --rm platform-runtime doctor
```

A camada de deployment separa software imutável de runtime state mutável; paths do host e secrets ficam fora do composition code versionado.

### Provider Minecraft incluído

Minecraft é um Provider de ambiente reutilizável de primeira parte. Task suites e composição científica permanecem downstream.

```bash
docker compose -f deploy/compose.yaml -f deploy/compose.minecraft.yaml build platform-runtime
docker compose -f deploy/compose.yaml -f deploy/compose.minecraft.yaml run --rm platform-runtime minecraft-doctor
```

[Minecraft infrastructure](docs/infrastructure/minecraft/README.md)

<!-- readme-section:repository-layout -->

## Estrutura do repositório

| Path | Responsibility |
| --- | --- |
| `research_platform/` | Implementação reutilizável e limites públicos do sistema |
| `configs/` | Exemplos de configuração versionados e templates sem segredos |
| `deploy/` | Imagem de container, runtime Compose e bootstrap de deployment |
| `docs/` | Documentação de architecture, infrastructure, governance, status e history |
| `scripts/` | Entradas finas de operator, audit, release e manutenção |
| `tests/` | Testes hierárquicos de regressão e contratos |
| `research_platform/environment/minecraft/` | Provider reutilizável de ambiente Minecraft |
| `LICENSE` / `NOTICE` / `THIRD_PARTY_NOTICES.md` | Avisos Apache-2.0 e licenças de terceiros |

`research_platform/` is the reusable package boundary; project-specific code stays downstream.

<!-- readme-section:testing -->

## Testes e verificação

Execute regressão e governance gates sobre a exact revision avaliada.

```bash
python -m pytest -q
python scripts/architecture_gate.py
python scripts/public_contract_audit.py
python scripts/no_degradation_audit.py
python scripts/check_readme_i18n.py
```

Um resultado verde histórico não prova a árvore atual. Execute novamente os gates relevantes para a exact revision que será publicada ou implantada.

O repositório usa uma taxonomia hierárquica de testes para atribuir cada teste a um contract level explícito e permitir que release evidence prove o que foi realmente exercitado. See `tests/TEST_SYSTEM.json`.

<!-- readme-section:principles -->

## Princípios de design

1. Um owner por durable state.
2. Composition antes de execution.
3. Runtime ports estreitos.
4. Effects externos carregam evidence.
5. Recovery é identity-aware.
6. Sem silent degradation.
7. Observation não é authority.
8. Mudanças de performance preservam semântica.
9. Documentação acompanha implementação.
10. Projetos permanecem downstream.

<!-- readme-section:extending -->

## Estendendo a plataforma

Adicione capacidades no menor limite de ownership possível. Se o contract público já existe, prefira um novo provider; adicione um contract apenas quando a capacidade em si for nova.

```text
<system>/
├── api/          public contracts and identities
├── runtime/      lifecycle and execution semantics
├── providers/    replaceable adapters owned by the system
└── composition/  provider-to-port binding
```

Evite wrappers genéricos que escondam algoritmos não relacionados, provider discovery ou effects externos atrás de uma única interface.

<!-- readme-section:documentation -->

## Documentação

Comece pelo índice de documentação.

### Referências principais

- [Documentation index](docs/INDEX.md)
- [Platform architecture](docs/architecture/PLATFORM_ARCHITECTURE.md)
- [Detailed system map](docs/architecture/VNEXT_DETAILED_SYSTEM_MAP.md)
- [Architecture migration contract](docs/architecture/FINAL_ARCHITECTURE_MIGRATION_CONTRACT.md)
- [Infrastructure documentation](docs/infrastructure/README.md)
- [Governance documentation](docs/governance/README.md)
- [Current status](docs/status/README.md)
- [Engineering history](docs/history/README.md)

Documentos de architecture definem ownership e contracts reutilizáveis; documentos de status descrevem a árvore atual; history preserva evidência do estado existente quando foi escrito.

<!-- readme-section:security -->

## Segurança e configuração

- Nunca faça commit de senhas, chaves privadas, tokens, runtime secrets ou credenciais locais.
- Mantenha paths específicos do host e secrets em profiles locais ignorados ou stores ligados ao ambiente.
- Prefira autenticação não assistida baseada em key/agent para automação remota.
- Comandos com effects externos devem ser typed, bounded, journaled e atribuídos a uma operation identity.
- Trate logs e evidence como dados operacionais potencialmente sensíveis.

<!-- readme-section:contributing -->

## Contribuindo

Mudanças devem ser revisáveis por ownership boundary e incluir tests e documentação suficientes para prová-las.

### Antes de abrir um Pull Request

```bash
python -m pytest -q
python scripts/architecture_gate.py
python scripts/check_readme_i18n.py
```

- preservar system ownership e public-contract boundaries
- adicionar ou atualizar cobertura de regressão focada
- atualizar documentação do owner no mesmo change set
- evitar refactors não relacionados no mesmo commit
- preservar fail-closed para effects externos incertos
- documentar explicitamente mudanças intencionais de semântica ou compatibilidade

[Documentation Change Policy](docs/governance/DOCUMENTATION_CHANGE_POLICY.md)

<!-- readme-section:license -->

## Licença

Noetrium é licenciado sob Apache License 2.0. O texto legal autoritativo é o arquivo LICENSE na raiz.

Componentes de terceiros continuam sob suas próprias licenças; consulte THIRD_PARTY_NOTICES.md. Pesos de modelos, datasets ou assets de benchmark distribuídos separadamente podem declarar termos próprios.

[`LICENSE`](LICENSE) · [`NOTICE`](NOTICE) · [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)

<!-- readme-section:status -->

## Status de desenvolvimento

A plataforma permanece em desenvolvimento ativo de arquitetura e runtime.

Para produção, publicação ou afirmações científicas, execute novamente os gates relevantes e examine release evidence vinculada à exact source revision em vez de confiar em um resultado verde histórico.

Mudanças históricas são mantidas intencionalmente fora deste README; use `docs/history/` para registros imutáveis de engenharia.

A fonte vigente do estado de desenvolvimento é `docs/status/CURRENT_DEVELOPMENT_BASELINE.md`; afirmações de release ou pesquisa devem estar vinculadas às evidências da revisão exata avaliada.

`docs/status/` · `docs/history/`
