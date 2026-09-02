# Noetrium directory architecture

This document defines the physical package layout for the reusable Noetrium
platform. It is a semantic layout, not a role-owned layout: roles remain a
governance ownership overlay from the playbook.

## Naming

The implementation package is named \`noetrium_platform\`. A package named
\`platform\` would collide with Python's standard-library \`platform\` module
and make imports environment-dependent. \`noetrium\` is the stable user-facing
facade; downstream code should prefer it for common workflows.

## Semantic planes

\`\`\`
noetrium_platform/
  foundation/       stable kernel, governance, scope, portfolio
  infrastructure/   lifecycle, resources, reliability
  capabilities/     model, participant, environment
  research/         execution and experimentation runtime
  evidence/         data, artifact, observability
  product/          operator and user-facing control contracts
\`\`\`

The planes are grouping boundaries, not global registries. Each subsystem keeps
its own explicit \`api\`, \`runtime\`, \`providers\`, and \`composition\`
surfaces only when those surfaces are semantically real.
## Components and dependency direction

Reusable downstream-facing method components live beside the platform:

\`\`\`
noetrium/
  components/reference/single_agent/  reusable cognition, memory, and tools
  orchestration/multi_agent/          multi-agent topology and coordination
  adapters/bridges/                   adapters for external agent frameworks
\`\`\`

The dependency direction is strictly one way:

\`\`\`
downstream method -> noetrium.contracts / noetrium.components -> explicit injected noetrium_platform implementation
\`\`\`

Single-agent components construct or execute one agent method. Multi-agent
orchestration is a higher layer: it coordinates agent nodes, messages, groups,
debates, and hierarchy, but does not own cognition, memory, model providers,
or scientific result truth.

## Extension rules

- Paper novelty stays in downstream repositories unless a mechanism is generic
  and independently reusable.
- Platform contracts are imported through public APIs and typed ports.
- Providers are explicitly composed and injected; no ambient service locator or
  mega-registry is introduced.
- One durable truth has one semantic authority and one writer.
- New directories require a semantic owner and a real contract; empty symmetry
  packages are not created.
- Role numbers describe review and governance responsibility, not import order
  or directory nesting.