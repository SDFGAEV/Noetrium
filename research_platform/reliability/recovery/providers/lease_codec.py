from __future__ import annotations

from dataclasses import asdict

from research_platform.platform.kernel.canonical import CanonicalEncodingError
from research_platform.platform.kernel.durability.document_integrity import DocumentIntegrityError
from research_platform.platform.kernel.durability.checksummed_document import (
    ChecksummedDocumentError,
    decode_checksummed_document,
    encode_checksummed_document,
)

from research_platform.reliability.recovery.api.lease import RecoveryLease


RECOVERY_LEASE_DOCUMENT_SCHEMA = "runtime-recovery-lease.v2"


class RecoveryLeaseIntegrityError(DocumentIntegrityError):
    pass


class RecoveryLeaseCodec:
    schema = RECOVERY_LEASE_DOCUMENT_SCHEMA

    def encode(self, lease: RecoveryLease) -> bytes:
        return encode_checksummed_document(self.schema, asdict(lease))

    def decode(self, raw: bytes) -> RecoveryLease:
        try:
            decoded = decode_checksummed_document(
                raw,
                expected_schema=self.schema,
            )
            return RecoveryLease(**decoded.payload)
        except ChecksummedDocumentError as exc:
            raise RecoveryLeaseIntegrityError.from_checksummed_document(
                exc, message="recovery lease document integrity failure"
            ) from exc
        except CanonicalEncodingError as exc:
            raise RecoveryLeaseIntegrityError(
                "recovery lease document contains non-canonical values"
            ) from exc
        except (KeyError, TypeError, ValueError) as exc:
            raise RecoveryLeaseIntegrityError("recovery lease violates the lease contract") from exc


__all__ = [
    "RECOVERY_LEASE_DOCUMENT_SCHEMA",
    "RecoveryLeaseCodec",
    "RecoveryLeaseIntegrityError",
]
