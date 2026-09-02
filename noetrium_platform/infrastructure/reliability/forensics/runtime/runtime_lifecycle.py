from __future__ import annotations

from dataclasses import dataclass

from noetrium_platform.infrastructure.reliability.forensics.api.runtime_parts import ForensicRuntimeParts


@dataclass(slots=True)
class ForensicRuntimeLifecycle:
    """Owns close ordering and lease release; resources themselves live in runtime parts."""

    parts: ForensicRuntimeParts
    closed: bool = False

    def close(self,flush_projections)->None:
        if self.closed:
            return
        error=None
        if self.parts.writer_lease is not None:
            try:
                flush_projections()
            except Exception as exc:
                error=exc
        try:
            self.parts.index.close()
        finally:
            if self.parts.writer_lease is not None:
                self.parts.writer_lease.release()
            self.closed=True
        if error is not None:
            raise error
