from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from research_platform.operator.api import (
    PROJECT_TEMPLATE_REVISION,
    ProjectCreateReceipt,
    ProjectCreateRequest,
)
from research_platform.operator.runtime.project_layout import project_package_name
from research_platform.operator.runtime.project_platform_identity import installed_platform_identity
from research_platform.platform.kernel.durability import InterprocessFileLock, atomic_replace_bytes
from research_platform.portfolio.api import (
    ProjectIdentity,
    ProjectManifest,
    ProjectSpec,
    ProjectToolProvenance,
    encode_project_manifest,
    project_manifest_document,
)

_MANIFEST_PATH = "project.manifest.json"


def _manifest(request: ProjectCreateRequest, platform_version: str, artifact_digest: str) -> ProjectManifest:
    return ProjectManifest(
        project=ProjectSpec(
            identity=ProjectIdentity(request.project_id, request.version),
            program_id=request.program_id,
            name=request.project_id,
        ),
        template_revision=PROJECT_TEMPLATE_REVISION,
        provenance=ProjectToolProvenance(
            tool_id="research-cli",
            tool_version=platform_version,
            platform_artifact_sha256=artifact_digest,
        ),
    )


def _pyproject(request: ProjectCreateRequest, package: str, platform_version: str) -> str:
    return f'''[build-system]\nrequires = ["setuptools>=69"]\nbuild-backend = "setuptools.build_meta"\n\n[project]\nname = "{request.project_id}"\nversion = "{request.version}"\nrequires-python = ">=3.11"\ndependencies = ["research-platform=={platform_version}"]\n\n[tool.setuptools.packages.find]\nwhere = ["src"]\ninclude = ["{package}*"]\n'''


def _project_module(request: ProjectCreateRequest) -> str:
    return f'''from research_platform.portfolio.api import ProjectIdentity\n\nPROJECT_IDENTITY = ProjectIdentity({request.project_id!r}, {request.version!r})\n\n__all__ = ["PROJECT_IDENTITY"]\n'''


def _requirements_module(request: ProjectCreateRequest) -> str:
    agent_digest = hashlib.sha256(
        f"{request.project_id}:{request.version}:agent".encode("utf-8")
    ).hexdigest()
    prompt_digest = hashlib.sha256(
        f"{request.project_id}:{request.version}:prompt".encode("utf-8")
    ).hexdigest()
    return f'''from research_platform.model.api import ModelCapabilityRequirement\nfrom research_platform.participant.api import AgentIdentity, AgentProjectDefinition\n\nAGENT_DEFINITION = AgentProjectDefinition(\n    role="agent",\n    identity=AgentIdentity(\n        agent_id={request.project_id!r},\n        implementation_version={request.version!r},\n        abi_version="1",\n        schema_version="1",\n        artifact_digest={agent_digest!r},\n    ),\n)\nPARTICIPANT_REQUIREMENT = AGENT_DEFINITION.requirement()\nMODEL_REQUIREMENT = ModelCapabilityRequirement(\n    role="agent",\n    prompt_generation_id="generation-1",\n    prompt_id="default",\n    prompt_digest={prompt_digest!r},\n)\n\n__all__ = ["AGENT_DEFINITION", "MODEL_REQUIREMENT", "PARTICIPANT_REQUIREMENT"]\n'''


def _participant_provider_module() -> str:
    return '''from research_platform.participant.api import (\n    ParticipantBindingDiagnostic,\n    ParticipantBindingDiagnosticCode,\n    ParticipantBindingDiagnosticSeverity,\n    ParticipantProjectBindingError,\n    ParticipantProviderProfile,\n    ParticipantRequirement,\n    ProjectParticipantBinding,\n    ProjectParticipantProviderPort,\n)\n\n\nclass ProjectParticipantProvider:\n    @property\n    def profile(self) -> ParticipantProviderProfile:\n        return ParticipantProviderProfile(\n            provider_id="project-participant",\n            supported_kinds=("agent",),\n        )\n\n    def diagnose(\n        self, requirement: ParticipantRequirement\n    ) -> tuple[ParticipantBindingDiagnostic, ...]:\n        return (\n            ParticipantBindingDiagnostic(\n                ParticipantBindingDiagnosticCode.RUNTIME_UNAVAILABLE,\n                ParticipantBindingDiagnosticSeverity.ERROR,\n                "configure a project Participant runtime binding",\n                requirement.digest(),\n                self.profile.provider_id,\n            ),\n        )\n\n    def bind(self, requirement: ParticipantRequirement) -> ProjectParticipantBinding:\n        raise ParticipantProjectBindingError(self.diagnose(requirement))\n\n\nPARTICIPANT_PROVIDER: ProjectParticipantProviderPort = ProjectParticipantProvider()\n'''


def _model_provider_module() -> str:
    return '''from research_platform.model.api import (\n    ModelBindingDiagnostic,\n    ModelBindingDiagnosticCode,\n    ModelBindingDiagnosticSeverity,\n    ModelCapabilityRequirement,\n    ModelProjectBindingError,\n    ModelProviderProfile,\n    ProjectModelClientPort,\n    ProjectModelProviderPort,\n)\n\n\nclass ProjectModelProvider:\n    @property\n    def profile(self) -> ModelProviderProfile:\n        return ModelProviderProfile(\n            provider_id="project-model",\n            capabilities=(),\n        )\n\n    def diagnose(\n        self, requirement: ModelCapabilityRequirement\n    ) -> tuple[ModelBindingDiagnostic, ...]:\n        return (\n            ModelBindingDiagnostic(\n                ModelBindingDiagnosticCode.QUALIFIED_BINDING_UNAVAILABLE,\n                ModelBindingDiagnosticSeverity.ERROR,\n                "configure a qualified project Model binding",\n                requirement.digest(),\n                self.profile.provider_id,\n            ),\n        )\n\n    def bind(self, requirement: ModelCapabilityRequirement) -> ProjectModelClientPort:\n        raise ModelProjectBindingError(self.diagnose(requirement))\n\n\nMODEL_PROVIDER: ProjectModelProviderPort = ProjectModelProvider()\n'''


def _environment_provider_module(request: ProjectCreateRequest) -> str:
    digest = hashlib.sha256(
        f"{request.project_id}:{request.version}:environment".encode("utf-8")
    ).hexdigest()
    return f'''from research_platform.environment.api import (\n    EnvironmentIdentity,\n    EnvironmentProviderCapabilities,\n    EnvironmentProviderPort,\n    EnvironmentSession,\n    EnvironmentSessionServices,\n)\n\n\nclass ProjectEnvironmentProvider:\n    @property\n    def identity(self) -> EnvironmentIdentity:\n        return EnvironmentIdentity(\n            environment_id={request.project_id!r},\n            implementation_version={request.version!r},\n            abi_version="1",\n            schema_version="1",\n            artifact_digest={digest!r},\n        )\n\n    @property\n    def capabilities(self) -> EnvironmentProviderCapabilities:\n        return EnvironmentProviderCapabilities()\n\n    def open_session(\n        self,\n        *,\n        session_id: str,\n        services: EnvironmentSessionServices,\n    ) -> EnvironmentSession:\n        del session_id, services\n        raise NotImplementedError("configure a project EnvironmentSession implementation")\n\n\nclass ProjectEnvironmentServices:\n    pass\n\n\nENVIRONMENT_SERVICES: EnvironmentSessionServices = ProjectEnvironmentServices()\nENVIRONMENT_PROVIDER: EnvironmentProviderPort = ProjectEnvironmentProvider()\n'''


def _application_module() -> str:
    return '''from pathlib import Path\n\nfrom research_platform.api import ResearchApplicationPort, bind_run_control_application\nfrom research_platform.experimentation.api import RunControlPort\n\n\ndef build_application(config_path: Path | None) -> ResearchApplicationPort:\n    del config_path\n    raise NotImplementedError("bind the project RunControlPort explicitly")\n\n\ndef bind_control(\n    control: RunControlPort, *, run_id: str, run_manifest_digest: str\n) -> ResearchApplicationPort:\n    return bind_run_control_application(\n        control, run_id=run_id, run_manifest_digest=run_manifest_digest\n    )\n'''


def _generated_test_module(package: str) -> str:
    return f'''import unittest\nfrom pathlib import Path\n\nfrom research_platform.environment.api import EnvironmentProviderPort\nfrom research_platform.model.api import ModelProjectBindingError, ProjectModelProviderPort\nfrom research_platform.participant.api import (\n    ParticipantProjectBindingError,\n    ProjectParticipantProviderPort,\n)\nfrom research_platform.portfolio.api import ProjectIdentity, decode_project_manifest_bytes\nfrom {package}.environment_provider import ENVIRONMENT_PROVIDER, ENVIRONMENT_SERVICES\nfrom {package}.model_provider import MODEL_PROVIDER\nfrom {package}.participant_provider import PARTICIPANT_PROVIDER\nfrom {package}.project import PROJECT_IDENTITY\nfrom {package}.requirements import MODEL_REQUIREMENT, PARTICIPANT_REQUIREMENT\n\nROOT = Path(__file__).resolve().parents[1]\n\n\nclass GeneratedProjectContractTests(unittest.TestCase):\n    def test_manifest_identity_matches_public_project_identity(self):\n        manifest = decode_project_manifest_bytes((ROOT / {_MANIFEST_PATH!r}).read_bytes())\n        self.assertIsInstance(PROJECT_IDENTITY, ProjectIdentity)\n        self.assertEqual(manifest.project.identity, PROJECT_IDENTITY)\n\n    def test_provider_templates_use_public_project_seams_and_fail_closed(self):\n        self.assertIsInstance(PARTICIPANT_PROVIDER, ProjectParticipantProviderPort)\n        diagnostics = PARTICIPANT_PROVIDER.diagnose(PARTICIPANT_REQUIREMENT)\n        self.assertTrue(diagnostics)\n        with self.assertRaises(ParticipantProjectBindingError):\n            PARTICIPANT_PROVIDER.bind(PARTICIPANT_REQUIREMENT)\n\n        self.assertIsInstance(MODEL_PROVIDER, ProjectModelProviderPort)\n        diagnostics = MODEL_PROVIDER.diagnose(MODEL_REQUIREMENT)\n        self.assertTrue(diagnostics)\n        with self.assertRaises(ModelProjectBindingError):\n            MODEL_PROVIDER.bind(MODEL_REQUIREMENT)\n\n        self.assertIsInstance(ENVIRONMENT_PROVIDER, EnvironmentProviderPort)\n        with self.assertRaises(NotImplementedError):\n            ENVIRONMENT_PROVIDER.open_session(\n                session_id="generated-test", services=ENVIRONMENT_SERVICES\n            )\n\n\nif __name__ == "__main__":\n    unittest.main()\n'''


def _readme(project_id: str) -> str:
    return f'''# {project_id}\n\nGenerated by `research project create` from `{PROJECT_TEMPLATE_REVISION}`.\n\n## Common project SDK\n\n`project.manifest.json` is canonical Portfolio-owned project truth. Start with the generated `project.py`, `requirements.py`, provider modules, and `application.py`; do not copy or modify Platform internals. The generated provider stubs consume public contracts and deliberately fail closed until real bindings are supplied.\n\nRun `research project doctor --project .` before integration and `research project test --project .` for the generated conformance tests. Lifecycle commands can load the project explicitly, for example `research run --project . <target> --payload '{"expected_generation":0}'`.\n\n## Advanced provider authors\n\nUse documented `<system>.api` contracts when implementing Participant/Model/Environment providers. Do not import `research_platform.*.runtime` or `research_platform.*.providers` from downstream project code, and do not persist replacement Platform lifecycle, checkpoint, model, resource, or evidence truth.\n'''


def _scaffold_files(request: ProjectCreateRequest) -> tuple[dict[str, bytes], str]:
    platform = installed_platform_identity()
    platform_version = platform.version
    manifest = _manifest(request, platform.version, platform.artifact_sha256)
    manifest_document = project_manifest_document(manifest)
    semantic_digest = str(manifest_document["semantic_digest"])
    package = project_package_name(request.project_id)
    text_files = {
        ".research-platform-template": PROJECT_TEMPLATE_REVISION + "\n",
        "README.md": _readme(request.project_id),
        "pyproject.toml": _pyproject(request, package, platform_version),
        f"src/{package}/__init__.py": "from .project import PROJECT_IDENTITY\n\n__all__ = [\"PROJECT_IDENTITY\"]\n",
        f"src/{package}/project.py": _project_module(request),
        f"src/{package}/requirements.py": _requirements_module(request),
        f"src/{package}/participant_provider.py": _participant_provider_module(),
        f"src/{package}/model_provider.py": _model_provider_module(),
        f"src/{package}/environment_provider.py": _environment_provider_module(request),
        f"src/{package}/application.py": _application_module(),
        "tests/test_generated_project_contracts.py": _generated_test_module(package),
    }
    files = {name: text.encode("utf-8") for name, text in text_files.items()}
    files[_MANIFEST_PATH] = encode_project_manifest(manifest)
    return files, semantic_digest


def _verify_existing(root: Path, files: dict[str, bytes]) -> None:
    for relative, expected in sorted(files.items()):
        target = root / relative
        if not target.is_file() or target.is_symlink() or target.read_bytes() != expected:
            raise ValueError(
                f"project destination is not the identical generated scaffold: {relative}"
            )


def _write_new_project(root: Path, files: dict[str, bytes]) -> None:
    root.mkdir(parents=False, exist_ok=False)
    marker = ".research-platform-template"
    ordered = [name for name in sorted(files) if name != marker]
    if marker in files:
        ordered.append(marker)
    try:
        for relative in ordered:
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            atomic_replace_bytes(target, files[relative])
    except BaseException:
        shutil.rmtree(root, ignore_errors=True)
        raise


def create_project(request: ProjectCreateRequest) -> ProjectCreateReceipt:
    files, semantic_digest = _scaffold_files(request)
    root = request.destination.expanduser().absolute()
    if root.is_symlink():
        raise ValueError("project destination must not be a symlink")
    root.parent.mkdir(parents=True, exist_ok=True)
    lock_path = root.parent / f".{root.name}.research-create.lock"
    with InterprocessFileLock(lock_path):
        if root.exists():
            if not root.is_dir():
                raise ValueError("project destination exists and is not a directory")
            _verify_existing(root, files)
        else:
            _write_new_project(root, files)
    return ProjectCreateReceipt(
        project_id=request.project_id,
        version=request.version,
        program_id=request.program_id,
        destination=str(root),
        template_revision=PROJECT_TEMPLATE_REVISION,
        manifest_path=_MANIFEST_PATH,
        manifest_semantic_digest=semantic_digest,
        generated_files=tuple(sorted(files)),
    )


__all__ = ["create_project"]
