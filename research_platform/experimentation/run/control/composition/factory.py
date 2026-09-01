from __future__ import annotations

from pathlib import Path

from research_platform.experimentation.run.api.artifacts import (
    RunArtifactVerificationPort,
    RunArtifactWriteActorPort,
)
from research_platform.experimentation.run.identity.api import RunIdentity
from research_platform.experimentation.run.manifest.api import RunLaunchManifest

from ..api import (
    RunControlCheckpointStorePort,
    RunControlEvidencePort,
    RunControlLifecyclePort,
    RunControlPort,
    RunControlReconciliationPort,
)
from ..providers import DirectoryRunControlLedger
from ..runtime import DurableRunControl


def build_durable_run_control(
    root: str | Path,
    *,
    identity: RunIdentity,
    manifest: RunLaunchManifest,
    writer_actor: RunArtifactWriteActorPort,
    lifecycle: RunControlLifecyclePort,
    checkpoint_store: RunControlCheckpointStorePort,
    reconciliation: RunControlReconciliationPort,
    evidence: RunControlEvidencePort,
    artifact_verifier: RunArtifactVerificationPort,
) -> RunControlPort:
    ledger = DirectoryRunControlLedger(
        root,
        run_id=identity.run_id,
        run_identity_digest=identity.digest(),
        run_manifest_digest=manifest.digest(),
        writer_actor=writer_actor,
    )
    return DurableRunControl(
        identity=identity,
        manifest=manifest,
        ledger=ledger,
        lifecycle=lifecycle,
        checkpoint_store=checkpoint_store,
        reconciliation=reconciliation,
        evidence=evidence,
        artifact_verifier=artifact_verifier,
    )


__all__ = ["build_durable_run_control"]
