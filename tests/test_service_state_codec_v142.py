from __future__ import annotations

from research_platform.runtime.service.api import ServiceProcessIdentity
from dataclasses import asdict, replace
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from research_platform.runtime.service.runtime.state_storage import FileServiceStateStore
from research_platform.platform.kernel.durability import ChecksummedDocumentFailureCode
from research_platform.runtime.service.runtime import (
    ServiceExitClass,
    ServiceStateIntegrityError,
    ServiceSupervisorState,
)


class ServiceStateCodecV142Tests(unittest.TestCase):
    def _state(self) -> ServiceSupervisorState:
        return replace(
            ServiceSupervisorState.initial("model.planner", "a" * 64),
            attempt=3,
            process=ServiceProcessIdentity(42, "pid:42:start:7", 42),
            last_exit_class=ServiceExitClass.SOFTWARE,
        )

    def test_new_document_is_versioned_checksummed_and_round_trips(self) -> None:
        with TemporaryDirectory() as td:
            path = Path(td) / "service.json"
            store = FileServiceStateStore(path)
            state = self._state()
            store.write(state)
            document = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(document["schema"], "service-supervisor-state.v3")
            self.assertEqual(len(document["payload_sha256"]), 64)
            self.assertEqual(store.read(), state)

    def test_payload_tampering_is_detected_before_state_construction(self) -> None:
        with TemporaryDirectory() as td:
            path = Path(td) / "service.json"
            store = FileServiceStateStore(path)
            store.write(self._state())
            document = json.loads(path.read_text(encoding="utf-8"))
            document["payload"]["attempt"] = 999
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaises(ServiceStateIntegrityError) as caught:
                store.read()
            self.assertIs(caught.exception.document_failure_code, ChecksummedDocumentFailureCode.CHECKSUM_MISMATCH)

    def test_unknown_future_schema_fails_closed(self) -> None:
        with TemporaryDirectory() as td:
            path = Path(td) / "service.json"
            path.write_text(json.dumps({"schema": "service-supervisor-state.v999"}), encoding="utf-8")
            with self.assertRaises(ServiceStateIntegrityError) as caught:
                FileServiceStateStore(path).read()
            self.assertIs(caught.exception.document_failure_code, ChecksummedDocumentFailureCode.UNSUPPORTED_SCHEMA)

    def test_unenveloped_state_is_rejected(self) -> None:
        with TemporaryDirectory() as td:
            path = Path(td) / "service.json"
            state = self._state()
            payload = asdict(state)
            payload["phase"] = state.phase.value
            payload["last_exit_class"] = int(state.last_exit_class)
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(ServiceStateIntegrityError) as caught:
                FileServiceStateStore(path).read()
            self.assertIs(caught.exception.document_failure_code, ChecksummedDocumentFailureCode.SCHEMA_MISSING)


class ServiceReadyAtV32Tests(unittest.TestCase):
    def _contract(self):
        from research_platform.runtime.service.api import ServiceLaunchContract
        return ServiceLaunchContract(
            "svc", "g1", "/opt/rp/python", ("/opt/rp/python", "-m", "svc"), "/srv/rp",
            "a" * 64, "b" * 64, "c" * 64, 10.0, 10.0, 1.0,
        )

    def test_ready_at_round_trips_as_independent_durable_authority(self):
        from research_platform.runtime.service.runtime import ServicePhase
        state = replace(
            ServiceSupervisorState.initial("svc", "d" * 64),
            phase=ServicePhase.RUNNING, ready_evidence_ref="ready:1", ready_at=1234.5,
        )
        with TemporaryDirectory() as td:
            store = FileServiceStateStore(Path(td) / "service.json")
            store.write(state)
            self.assertEqual(store.read().ready_at, 1234.5)

    def test_ready_evidence_without_ready_at_fails_durable_encoding(self):
        state = replace(ServiceSupervisorState.initial("svc", "d" * 64), ready_evidence_ref="ready:1")
        with TemporaryDirectory() as td:
            with self.assertRaises(ServiceStateIntegrityError):
                FileServiceStateStore(Path(td) / "service.json").write(state)


class ServiceReadyProjectionV32Tests(unittest.TestCase):
    def test_producer_ready_at_is_persisted_preserved_and_publicly_projected(self):
        from unittest.mock import patch
        from research_platform.runtime.service.api import (
            ServiceLaunchContract, ServiceProcessIdentity, ServiceReconcileObservation,
        )
        from research_platform.runtime.service.runtime import ServicePhase
        from research_platform.runtime.service.runtime.runtime_endpoint import ExactServiceRuntimeEndpoint
        from research_platform.runtime.service.runtime.start_flow_common import ServiceReadinessCommitter
        from research_platform.runtime.service.runtime.state_transition import ServiceStateTransitionWriter

        contract = ServiceLaunchContract(
            "svc", "g1", "/opt/rp/python", ("/opt/rp/python", "-m", "svc"), "/srv/rp",
            "a" * 64, "b" * 64, "c" * 64, 10.0, 10.0, 1.0,
        )
        process = ServiceProcessIdentity(42, "start:42")

        class Store:
            def __init__(self): self.state = None
            def write(self, state): self.state = state
        class Adapter:
            def wait_ready(self, observed_process, observed_contract):
                self.assertions = (observed_process, observed_contract)
                return "ready:producer", "stdout:producer", "stderr:producer"

        store = Store(); adapter = Adapter()
        transitions = ServiceStateTransitionWriter(store)
        committer = ServiceReadinessCommitter(adapter, transitions)
        initial = ServiceSupervisorState.initial(contract.service_id, contract.digest())
        with patch("research_platform.runtime.service.runtime.start_flow_common.time.time", return_value=1777.25):
            state, _refs = committer.commit(contract, initial, process)
        self.assertEqual(state.ready_at, 1777.25)
        self.assertEqual(state.last_heartbeat_at, 1777.25)
        heartbeat = transitions.persist(state, ServicePhase.RUNNING, last_heartbeat_at=1888.0)
        self.assertEqual(heartbeat.ready_at, 1777.25)

        class Supervisor:
            def observe_state(self, observed_contract): return heartbeat
            def reconcile_exact(self, observed_contract):
                return ServiceReconcileObservation(True, process, ("reconcile:producer",))
        observation = ExactServiceRuntimeEndpoint(Supervisor()).verify_ready_exact(contract)
        self.assertEqual(observation.ready_at, 1777.25)
        self.assertEqual(observation.ready_evidence_ref, "ready:producer")


if __name__ == "__main__":
    unittest.main()
