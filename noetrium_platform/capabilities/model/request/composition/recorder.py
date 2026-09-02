from __future__ import annotations

from pathlib import Path

from ..runtime import (
    DirectoryContentAddressedStore,
    DirectoryModelRequestLedger,
    ReconstructableModelRequestRecorder,
)


def build_directory_model_request_recorder(root: Path) -> ReconstructableModelRequestRecorder:
    """Compose the durable request recorder behind the request-system API."""

    return ReconstructableModelRequestRecorder(
        DirectoryContentAddressedStore(root / "blobs"),
        DirectoryModelRequestLedger(root / "requests"),
    )


__all__ = ["build_directory_model_request_recorder"]
