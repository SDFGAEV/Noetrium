from __future__ import annotations

from collections.abc import Mapping

from noetrium_platform.foundation.governance.system_registry.api import SystemIdentity
from noetrium_platform.evidence.observability.logging.query.api import LogQueryPort
from noetrium_platform.evidence.observability.logging.record.api import (
    ExceptionDescriptorPort,
    LogLevel,
    LogRecord,
    LogWriterPort,
    LoggingSystemPort,
)
from noetrium_platform.evidence.observability.logging.record.runtime.logger import StructuredLogger
from noetrium_platform.evidence.observability.logging.sink.api import LogSinkPort
from noetrium_platform.evidence.observability.logging.context.api import DiagnosticAddress
from noetrium_platform.foundation.scope.api import ScopeIdentity
from noetrium_platform.foundation.kernel.kernel import JsonValue


class StructuredLoggingSystem(LoggingSystemPort):
    """Composes leaf seams without owning storage or query implementations."""

    def __init__(
        self,
        sink: LogSinkPort,
        query: LogQueryPort,
        *,
        exception_descriptor: ExceptionDescriptorPort | None = None,
    ) -> None:
        self._sink = sink
        self._query = query
        self._exception_descriptor = exception_descriptor

    def bind(
        self,
        *,
        logger: str,
        address: DiagnosticAddress,
        attributes: Mapping[str, JsonValue] | None = None,
    ) -> LogWriterPort:
        return StructuredLogger(
            self._sink,
            logger=logger,
            address=address,
            attributes=attributes,
            exception_descriptor=self._exception_descriptor,
        )

    def query(
        self,
        *,
        scope: ScopeIdentity | None = None,
        system: SystemIdentity | None = None,
        component_id: str | None = None,
        trace_id: str | None = None,
        level_at_least: LogLevel | None = None,
        event: str | None = None,
        limit: int = 1000,
    ) -> tuple[LogRecord, ...]:
        return self._query.query(
            scope=scope,
            system=system,
            component_id=component_id,
            trace_id=trace_id,
            level_at_least=level_at_least,
            event=event,
            limit=limit,
        )


__all__ = ["StructuredLoggingSystem"]
