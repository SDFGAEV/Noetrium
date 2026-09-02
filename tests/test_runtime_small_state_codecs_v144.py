from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import time
import unittest

from noetrium_platform.capabilities.model.serving.api import ServiceHeartbeat
from noetrium_platform.foundation.kernel.kernel.durability import ChecksummedDocumentFailureCode
from noetrium_platform.research.execution.runtime.manager.heartbeat_storage import FileServiceHeartbeatStore
from noetrium_platform.infrastructure.reliability.recovery.providers.lease_store import RecoveryLeaseStore
from noetrium_platform.research.execution.runtime.manager.heartbeat_codec import ServiceHeartbeatIntegrityError
from noetrium_platform.infrastructure.reliability.recovery.providers.lease_codec import RecoveryLeaseIntegrityError


class RuntimeSmallStateCodecV144Tests(unittest.TestCase):
    def test_recovery_lease_is_checksummed_and_rejects_unenveloped_state(self) -> None:
        with TemporaryDirectory() as td:
            path = Path(td) / "lease.json"
            store = RecoveryLeaseStore(path)
            lease = store.acquire("owner", "manifest", ttl_seconds=10, now=1)
            document = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(document["schema"], "runtime-recovery-lease.v2")
            self.assertEqual(store.read(), lease)

            path.write_text(json.dumps(asdict(lease)), encoding="utf-8")
            with self.assertRaises(RecoveryLeaseIntegrityError) as caught:
                store.read()
            self.assertIs(caught.exception.document_failure_code, ChecksummedDocumentFailureCode.SCHEMA_MISSING)

    def test_recovery_lease_tamper_is_detected(self) -> None:
        with TemporaryDirectory() as td:
            path = Path(td) / "lease.json"
            store = RecoveryLeaseStore(path)
            store.acquire("owner", "manifest", ttl_seconds=10, now=1)
            document = json.loads(path.read_text(encoding="utf-8"))
            document["payload"]["owner_id"] = "attacker"
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaises(RecoveryLeaseIntegrityError) as caught:
                store.read()
            self.assertIs(caught.exception.document_failure_code, ChecksummedDocumentFailureCode.CHECKSUM_MISMATCH)

    def test_heartbeat_is_checksummed_and_rejects_unenveloped_state(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            store = FileServiceHeartbeatStore(root)
            heartbeat = ServiceHeartbeat(
                "d1", "stack", 123, "start", "argv", True, "qualification", time.time()
            )
            store.write(heartbeat)
            path = root / "d1.json"
            document = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(document["schema"], "service-heartbeat.v2")
            self.assertEqual(store.read("d1"), heartbeat)

            path.write_text(json.dumps(asdict(heartbeat)), encoding="utf-8")
            with self.assertRaises(ServiceHeartbeatIntegrityError) as caught:
                store.read("d1")
            self.assertIs(caught.exception.document_failure_code, ChecksummedDocumentFailureCode.SCHEMA_MISSING)

    def test_heartbeat_tamper_is_detected(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            store = FileServiceHeartbeatStore(root)
            heartbeat = ServiceHeartbeat(
                "d1", "stack", 123, "start", "argv", True, "qualification", time.time()
            )
            store.write(heartbeat)
            path = root / "d1.json"
            document = json.loads(path.read_text(encoding="utf-8"))
            document["payload"]["ready"] = False
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaises(ServiceHeartbeatIntegrityError) as caught:
                store.read("d1")
            self.assertIs(caught.exception.document_failure_code, ChecksummedDocumentFailureCode.CHECKSUM_MISMATCH)


if __name__ == "__main__":
    unittest.main()
