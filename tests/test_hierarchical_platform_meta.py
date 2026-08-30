import pytest

from research_platform.experimentation.catalog.runtime import InMemoryExperimentationCatalog
from research_platform.experimentation.experiment.api import ExperimentSpec
from research_platform.experimentation.run.identity.api import RunIdentity
from research_platform.experimentation.study import StudySpec
from research_platform.portfolio.api import (
    ProgramSpec,
    ProjectCapabilityRequirement,
    ProjectConfigurationReference,
    ProjectIdentity,
    ProjectManifest,
    ProjectManifestDecodeError,
    ProjectMethodRequirement,
    ProjectProviderBinding,
    ProjectSpec,
    ProjectToolProvenance,
    WorkspaceSpec,
    decode_project_manifest_bytes,
    decode_project_manifest_document,
    encode_project_manifest,
    project_manifest_document,
)
from research_platform.portfolio.runtime import InMemoryPortfolioCatalog
from research_platform.environment.catalog.api import (
    EnvironmentAssignment,
    EnvironmentOverlay,
    EnvironmentSpec,
    ExecutionEnvironmentKind,
)
from research_platform.environment.catalog.runtime import ExecutionEnvironmentCatalog
from research_platform.scope.api import ScopeIdentity, ScopeKind
from research_platform.scope.runtime import InMemoryScopeRegistry


EXAMPLE_TEMPLATE_REVISION = "research-project-template.v1"


def _project_tool_provenance() -> ProjectToolProvenance:
    return ProjectToolProvenance("research", "1.0.0", "a" * 64)


def test_scope_portfolio_experiment_run_hierarchy_is_explicit():
    scopes = InMemoryScopeRegistry()
    portfolio = InMemoryPortfolioCatalog(scopes)
    portfolio.register_workspace(WorkspaceSpec("ws", "Workspace"))
    portfolio.register_program(ProgramSpec("prog", "ws", "Program"))
    portfolio.register_project(ProjectManifest(
        ProjectSpec(ProjectIdentity("paper", "1.0.0"), "prog", "Paper"),
        EXAMPLE_TEMPLATE_REVISION,
        _project_tool_provenance(),
        study_ids=("main",),
    ))

    experiments = InMemoryExperimentationCatalog(scopes)
    study = StudySpec("main", "paper", "Main", ("exp",))
    experiments.register_study(study)
    experiment = ExperimentSpec(
        experiment_id="exp",
        study_id="main",
        project_id="paper",
        participants=(),
        model_stack_digest="m",
        prompt_generation="p",
        workload_digest="w",
        seed_digest="s",
        repetitions=1,
        scientific_workflow_id="wf",
    )
    experiments.register_experiment(experiment)
    run = RunIdentity("run-1", "session-1", "trace-1")
    experiments.register_run("exp", run)

    assert [item.kind for item in scopes.ancestry(run.scope)] == [
        ScopeKind.RUN,
        ScopeKind.EXPERIMENT,
        ScopeKind.STUDY,
        ScopeKind.PROJECT,
        ScopeKind.PROGRAM,
        ScopeKind.WORKSPACE,
        ScopeKind.PLATFORM,
    ]


def test_environment_assignment_inherits_and_overlay_merges_without_copying_envs():
    scopes = InMemoryScopeRegistry()
    ws = ScopeIdentity(ScopeKind.WORKSPACE, "ws")
    project = ScopeIdentity(ScopeKind.PROJECT, "paper")
    study = ScopeIdentity(ScopeKind.STUDY, "study")
    scopes.register(ws, ScopeIdentity(ScopeKind.PLATFORM, "default"))
    program = ScopeIdentity(ScopeKind.PROGRAM, "prog")
    scopes.register(program, ws)
    scopes.register(project, program)
    scopes.register(study, project)

    catalog = ExecutionEnvironmentCatalog(scopes)
    base = EnvironmentSpec(
        "base",
        ExecutionEnvironmentKind.PYTHON,
        ws,
        requirements=(("python", "3.12"), ("torch", "2.6")),
    )
    sem = EnvironmentSpec(
        "sem",
        ExecutionEnvironmentKind.PYTHON,
        project,
        parent_spec_id="base",
        requirements=(("faiss", "1"),),
    )
    catalog.register_spec(base)
    catalog.register_spec(sem)
    catalog.assign(EnvironmentAssignment("method", "sem", project))
    catalog.register_overlay(EnvironmentOverlay("study-debug", "sem", study, requirements=(("debugpy", "1"),)))

    resolved = catalog.resolve("method", study)
    assert resolved.source_spec_ids == ("base", "sem")
    assert dict(resolved.requirements) == {"python": "3.12", "torch": "2.6", "faiss": "1", "debugpy": "1"}
    assert resolved.applied_overlay_ids == ("study-debug",)

def _project_manifest_fixture() -> ProjectManifest:
    return ProjectManifest(
        ProjectSpec(
            ProjectIdentity("example-project", "1.2.0"),
            "prog",
            "Example Project",
            tags=("example",),
        ),
        EXAMPLE_TEMPLATE_REVISION,
        _project_tool_provenance(),
        capability_requirements=(
            ProjectCapabilityRequirement(
                "logging",
                "observability.logging",
                "system",
                1,
                "1" * 64,
            ),
        ),
        provider_bindings=(
            ProjectProviderBinding(
                "logging-default", "logging", "reference.logging", "1.0.0", "3" * 64
            ),
        ),
        method_requirements=(ProjectMethodRequirement("baseline", "control"),),
        configuration_refs=(
            ProjectConfigurationReference("main-config", "configs/main.json", "2" * 64),
        ),
        study_ids=("main",),
    )


def test_project_manifest_is_strict_canonical_digest_bound_and_single_authority() -> None:
    from research_platform.portfolio.project.api import ProjectIdentity as LeafProjectIdentity
    from research_platform.portfolio.project.api import ProjectManifest as LeafProjectManifest

    manifest = _project_manifest_fixture()
    raw = encode_project_manifest(manifest)
    decoded = decode_project_manifest_bytes(raw)
    assert decoded == manifest
    assert decoded.semantic_digest == manifest.semantic_digest
    assert project_manifest_document(decoded)["semantic_digest"] == manifest.semantic_digest
    assert LeafProjectManifest is ProjectManifest
    assert LeafProjectIdentity is ProjectIdentity
    assert manifest.binding_inputs == manifest.capability_requirements


def test_project_manifest_digest_changes_with_project_configuration_truth() -> None:
    manifest = _project_manifest_fixture()
    changed = ProjectManifest(
        project=manifest.project,
        template_revision=manifest.template_revision,
        provenance=manifest.provenance,
        capability_requirements=manifest.capability_requirements,
        provider_bindings=manifest.provider_bindings,
        method_requirements=manifest.method_requirements,
        configuration_refs=(
            ProjectConfigurationReference("main-config", "configs/main.json", "3" * 64),
        ),
        study_ids=manifest.study_ids,
    )
    assert changed.semantic_digest != manifest.semantic_digest


def test_project_manifest_decoder_rejects_unknown_nonfinite_and_digest_drift() -> None:
    manifest = _project_manifest_fixture()
    document = dict(project_manifest_document(manifest))
    document["unknown"] = "value"
    with pytest.raises(ProjectManifestDecodeError, match="fields are not exact"):
        decode_project_manifest_document(document)

    for nonfinite in (float("nan"), float("inf"), float("-inf")):
        document = dict(project_manifest_document(manifest))
        document["unknown"] = nonfinite
        with pytest.raises(ProjectManifestDecodeError, match="non-finite"):
            decode_project_manifest_document(document)

    document = dict(project_manifest_document(manifest))
    document["schema"] = "research-platform.project-manifest.v999"
    with pytest.raises(ProjectManifestDecodeError, match="unsupported project manifest schema"):
        decode_project_manifest_document(document)

    document = dict(project_manifest_document(manifest))
    project = dict(document["project"])
    project["name"] = "Tampered"
    document["project"] = project
    with pytest.raises(ProjectManifestDecodeError, match="semantic digest mismatch"):
        decode_project_manifest_document(document)


def test_project_manifest_bytes_reject_duplicate_keys_and_noncanonical_identity() -> None:
    with pytest.raises(ProjectManifestDecodeError, match="duplicate JSON key"):
        decode_project_manifest_bytes(b'{"schema":"x","schema":"y"}')
    document = dict(project_manifest_document(_project_manifest_fixture()))
    project = dict(document["project"])
    identity = dict(project["identity"])
    identity["project_id"] = "Bad Project"
    project["identity"] = identity
    document["project"] = project
    with pytest.raises(ProjectManifestDecodeError, match="project_id"):
        decode_project_manifest_document(document)

def test_project_manifest_binds_template_tool_provenance_and_provider_choices() -> None:
    manifest = _project_manifest_fixture()
    document = project_manifest_document(manifest)
    assert document["template_revision"] == EXAMPLE_TEMPLATE_REVISION
    assert document["provenance"]["tool_id"] == "research"
    assert document["provenance"]["platform_artifact_sha256"] == "a" * 64
    assert document["provider_bindings"][0]["binding_id"] == "logging-default"

    changed = ProjectManifest(
        project=manifest.project,
        template_revision=manifest.template_revision,
        provenance=ProjectToolProvenance("research", "1.0.0", "b" * 64),
        capability_requirements=manifest.capability_requirements,
        provider_bindings=manifest.provider_bindings,
        method_requirements=manifest.method_requirements,
        configuration_refs=manifest.configuration_refs,
        study_ids=manifest.study_ids,
    )
    assert changed.semantic_digest != manifest.semantic_digest


def test_project_manifest_records_product_owned_template_revision_without_owning_compatibility() -> None:
    manifest = _project_manifest_fixture()
    future_revision = "research-project-template.v999"
    future = ProjectManifest(
        project=manifest.project,
        template_revision=future_revision,
        provenance=manifest.provenance,
        capability_requirements=manifest.capability_requirements,
        provider_bindings=manifest.provider_bindings,
        method_requirements=manifest.method_requirements,
        configuration_refs=manifest.configuration_refs,
        study_ids=manifest.study_ids,
    )
    decoded = decode_project_manifest_bytes(encode_project_manifest(future))
    assert decoded.template_revision == future_revision
    assert decoded.semantic_digest == future.semantic_digest

    for invalid in ("", " research-project-template.v1", "research-project-template.v1 "):
        with pytest.raises(ValueError, match="template_revision"):
            ProjectManifest(
                project=manifest.project,
                template_revision=invalid,
                provenance=manifest.provenance,
            )


def test_project_manifest_rejects_duplicate_provider_binding_identity() -> None:
    manifest = _project_manifest_fixture()
    duplicate = ProjectProviderBinding(
        "logging-default", "logging", "another.logging", "1.0.0", "4" * 64
    )
    with pytest.raises(ValueError, match="provider binding ids must be unique"):
        ProjectManifest(
            project=manifest.project,
            template_revision=manifest.template_revision,
            provenance=manifest.provenance,
            capability_requirements=manifest.capability_requirements,
            provider_bindings=(*manifest.provider_bindings, duplicate),
        )


def test_project_manifest_bytes_require_exact_canonical_encoding() -> None:
    raw = encode_project_manifest(_project_manifest_fixture())
    assert decode_project_manifest_bytes(raw) == _project_manifest_fixture()
    with pytest.raises(ProjectManifestDecodeError, match="bytes are not canonical JSON"):
        decode_project_manifest_bytes(b" " + raw)
