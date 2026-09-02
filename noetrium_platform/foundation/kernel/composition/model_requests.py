from __future__ import annotations

from pathlib import Path

from noetrium_platform.capabilities.model.request.runtime import (
    DirectoryContentAddressedStore,
    DirectoryModelRequestLedger,
    ReconstructableModelRequestRecorder,
)


def build_directory_model_request_recorder(root: Path) -> ReconstructableModelRequestRecorder:
    """Default durable model-request backend wiring.

    Composition owns storage layout. Prompt/model-request contracts know nothing
    about directories, file formats, or the concrete persistence backend.
    """
    root = Path(root)
    return ReconstructableModelRequestRecorder(
        DirectoryContentAddressedStore(root / "content"),
        DirectoryModelRequestLedger(root / "requests"),
    )


__all__ = ["build_directory_model_request_recorder"]
