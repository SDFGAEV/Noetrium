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
  <strong>Français</strong> ·
  <a href="README.de.md">Deutsch</a> ·
  <a href="README.ru.md">Русский</a>
</p>
<!-- readme-nav:end -->



<!-- readme-locale:fr -->

<!-- readme-source-sha256:9dd7f68d71e7c6bfc9c059ec68315c5e86dc1ccac0a179645d1e0879c40c283f -->



**Infrastructure pilotée par contrats pour la recherche reproductible sur les agents IA.**



[![Python](https://img.shields.io/badge/Python-%3E%3D3.11-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Version](https://img.shields.io/badge/version-0.43.1-blue)](pyproject.toml)
[![Architecture](https://img.shields.io/badge/architecture-contract--driven-6f42c1)](docs/architecture/PLATFORM_ARCHITECTURE.md)
[![License](https://img.shields.io/badge/license-Apache--2.0-green)](LICENSE)



<!-- readme-section:overview -->

## Vue d'ensemble

Noetrium est une plateforme indépendante des projets pour construire, exécuter, restaurer, observer, optimiser et auditer des systèmes d'agents IA de longue durée et des charges de recherche.

L'infrastructure réutilisable reste dans la plateforme ; la sémantique scientifique propre aux articles, les benchmarks, matrices expérimentales et politiques de déploiement restent dans les projets downstream.

<!-- readme-section:why -->

## Pourquoi cette plateforme ?

Les systèmes d'agents de longue durée échouent de davantage de façons que les scripts ordinaires : crash de processus, effets externes incertains, dérive d'environnement, changements de déploiement de modèles, checkpoints incompatibles et logs partiels pris à tort pour des preuves valides.

La plateforme modélise ces problèmes comme des systèmes explicites avec typed contracts, ownership stable, identités durables, effets porteurs de preuves et récupération fail-closed.

<!-- readme-section:capabilities -->

## Capacités principales

- Architecture récursive — ownership explicite, API publiques étroites, typed ports et provider binding à la composition.
- Infrastructure d'expérimentation — Study, Run, Branch, Task, Variant, Workload, Checkpoint, Resume et identités de reproductibilité.
- Runtime Agent — frontières Participant, Capability, Action, Memory, Workflow et Execution sans lookup global caché.
- Infrastructure modèle — catalog, revision, qualification, serving identity, request envelope et prompt binding.
- Infrastructure environnement — specification, lifecycle, readiness, observation, effects, snapshots et recovery.
- Runtime processus/serveur — supervision, sessions, toolchains, exécution distante, contrôle du lifecycle et journals.
- Données/Artifacts durables — état checksummé, récupération WAL, lineage, retention et preuves content-addressed.
- Fiabilité — classification des échecs, effect certainty, reconciliation, replay, incidents et récupération fail-closed.
- Observabilité — logs structurés, events, metrics, traces, diagnostics, projections et signaux de santé.
- Gouvernance — gates architecture, dependency, algorithm, concurrency, performance, forensic, release et no-degradation.

<!-- readme-section:architecture -->

## Architecture

Composition, Execution et Observation sont des plans d'autorité séparés.

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

Le runtime ne découvre pas les providers via un service locator global. Observability n'est pas un second command bus. Chaque durable state possède un seul owner et les effets externes restent UNKNOWN jusqu'à preuve par reconciliation.

`research_platform/governance/system_registry/catalog.json`

<!-- readme-section:downstream -->

## Plateforme et projets downstream

Ce dépôt est un package de plateforme réutilisable et indépendant. Méthodes de recherche, task suites, composition d'environnement spécifique, matrices expérimentales, choix de modèles, inventaires de déploiement et interprétation scientifique appartiennent aux projets downstream.

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

Le code downstream consomme les contracts publics de la plateforme et fournit ses propres implémentations ; la plateforme ne doit pas importer un projet downstream pour décider du sens scientifique ou de la politique de déploiement.

<!-- readme-section:quick-start -->

## Démarrage rapide

### Prérequis

- Python 3.11 ou plus récent
- Git
- Docker / Docker Compose pour les workflows conteneurisés
- Runtimes externes optionnels uniquement pour les Providers qui les exigent explicitement

### Installation pour le développement

```bash
git clone git@github.com:SDFGAEV/noetrium.git
cd noetrium
python -m venv .venv
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
```

### Inspecter la plateforme

```bash
research-platform-architecture-gate
research-platform-algorithm --help
research-platform-concurrency --help
research-platform-performance --help
research-platform-manage --help
```

<!-- readme-section:containers -->

## Workflow conteneur

Une image Linux réutilisable et une définition Compose sont maintenues sous `deploy/`.

```bash
cp deploy/.env.example deploy/.env
docker compose -f deploy/compose.yaml config
docker compose -f deploy/compose.yaml build
docker compose -f deploy/compose.yaml run --rm platform-runtime doctor
```

La couche de deployment sépare le logiciel immuable du runtime state mutable ; paths hôte et secrets restent hors du composition code versionné.

### Provider Minecraft inclus

Minecraft est un Provider d'environnement réutilisable first-party. Task suites et composition scientifique restent downstream.

```bash
docker compose -f deploy/compose.yaml -f deploy/compose.minecraft.yaml build platform-runtime
docker compose -f deploy/compose.yaml -f deploy/compose.minecraft.yaml run --rm platform-runtime minecraft-doctor
```

[Minecraft infrastructure](docs/infrastructure/minecraft/README.md)

<!-- readme-section:repository-layout -->

## Structure du dépôt

| Path | Responsibility |
| --- | --- |
| `research_platform/` | Implémentation réutilisable et frontières publiques des systèmes |
| `configs/` | Exemples de configuration versionnés et modèles sans secrets |
| `deploy/` | Image conteneur, runtime Compose et bootstrap de déploiement |
| `docs/` | Documentation architecture, infrastructure, governance, status et history |
| `scripts/` | Entrées fines operator, audit, release et maintenance |
| `tests/` | Tests hiérarchiques de régression et de contrats |
| `research_platform/environment/minecraft/` | Provider d'environnement Minecraft réutilisable |
| `LICENSE` / `NOTICE` / `THIRD_PARTY_NOTICES.md` | Avis Apache-2.0 et licences tierces |

`research_platform/` is the reusable package boundary; project-specific code stays downstream.

<!-- readme-section:testing -->

## Tests et vérification

Exécutez la régression et les governance gates sur l'exact revision évaluée.

```bash
python -m pytest -q
python scripts/architecture_gate.py
python scripts/public_contract_audit.py
python scripts/no_degradation_audit.py
python scripts/check_readme_i18n.py
```

Un résultat vert historique ne prouve pas l'arbre actuel. Relancez les gates pertinents pour l'exact revision que vous souhaitez publier ou déployer.

Le dépôt utilise une taxonomie hiérarchique des tests afin que chaque test appartienne à un contract level explicite et que release evidence puisse prouver ce qui a réellement été exécuté. See `tests/TEST_SYSTEM.json`.

<!-- readme-section:principles -->

## Principes de conception

1. Un owner par durable state.
2. Composition avant execution.
3. Runtime ports étroits.
4. Les effets externes portent des evidence.
5. Recovery est identity-aware.
6. Aucune silent degradation.
7. Observation n'est pas authority.
8. Les optimisations préservent la sémantique.
9. La documentation évolue avec l'implémentation.
10. Les projets restent downstream.

<!-- readme-section:extending -->

## Étendre la plateforme

Ajoutez une capacité à la plus petite frontière de ownership. Si le contract public existe déjà, préférez un nouveau provider ; n'ajoutez un contract que lorsque la capacité elle-même est nouvelle.

```text
<system>/
├── api/          public contracts and identities
├── runtime/      lifecycle and execution semantics
├── providers/    replaceable adapters owned by the system
└── composition/  provider-to-port binding
```

Évitez les wrappers génériques qui cachent des algorithmes sans rapport, provider discovery ou des effets externes derrière une seule interface.

<!-- readme-section:documentation -->

## Documentation

Commencez par l'index de documentation.

### Références principales

- [Documentation index](docs/INDEX.md)
- [Platform architecture](docs/architecture/PLATFORM_ARCHITECTURE.md)
- [Detailed system map](docs/architecture/VNEXT_DETAILED_SYSTEM_MAP.md)
- [Architecture migration contract](docs/architecture/FINAL_ARCHITECTURE_MIGRATION_CONTRACT.md)
- [Infrastructure documentation](docs/infrastructure/README.md)
- [Governance documentation](docs/governance/README.md)
- [Current status](docs/status/README.md)
- [Engineering history](docs/history/README.md)

Les documents d'architecture définissent ownership et contracts réutilisables ; les documents de status décrivent l'arbre actuel ; history conserve les preuves de l'état existant lors de leur rédaction.

<!-- readme-section:security -->

## Sécurité et configuration

- Ne committez jamais mots de passe, clés privées, tokens, runtime secrets ou credentials locales.
- Gardez paths spécifiques aux hôtes et secrets dans des profils locaux ignorés ou stores liés à l'environnement.
- Préférez une authentification non interactive par key/agent pour l'automatisation distante.
- Les commandes à effets externes doivent être typed, bounded, journaled et attribuables à une operation identity.
- Considérez logs et evidence comme des données opérationnelles potentiellement sensibles.

<!-- readme-section:contributing -->

## Contribuer

Les changements doivent être révisables par ownership boundary et inclure les tests et la documentation nécessaires pour les prouver.

### Avant d'ouvrir une Pull Request

```bash
python -m pytest -q
python scripts/architecture_gate.py
python scripts/check_readme_i18n.py
```

- préserver system ownership et public-contract boundaries
- ajouter ou mettre à jour une couverture de régression ciblée
- mettre à jour la documentation de l'owner dans le même change set
- éviter les refactors sans rapport dans le même commit
- préserver fail-closed pour les effets externes incertains
- documenter explicitement tout changement volontaire de sémantique ou compatibilité

[Documentation Change Policy](docs/governance/DOCUMENTATION_CHANGE_POLICY.md)

<!-- readme-section:license -->

## Licence

Noetrium est sous Apache License 2.0. Le texte juridique faisant autorité est le fichier LICENSE à la racine.

Les composants tiers restent régis par leurs propres licences ; voir THIRD_PARTY_NOTICES.md. Les poids de modèles, datasets ou assets de benchmark distribués séparément peuvent déclarer des conditions distinctes.

[`LICENSE`](LICENSE) · [`NOTICE`](NOTICE) · [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)

<!-- readme-section:status -->

## État du développement

La plateforme reste en développement actif d'architecture et de runtime.

Pour la production, la publication ou les affirmations scientifiques, relancez les gates pertinents et examinez release evidence liée à l'exact source revision plutôt que de vous fier à un ancien résultat vert.

Les changements historiques sont volontairement exclus de ce README ; utilisez `docs/history/` pour les archives d’ingénierie immuables.

La source de vérité de l’état de développement est `docs/status/CURRENT_DEVELOPMENT_BASELINE.md` ; toute affirmation de publication ou de recherche doit être liée aux preuves de la révision exacte évaluée.

`docs/status/` · `docs/history/`
