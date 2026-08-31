# ROLE02 PGE runtime conformance — 2026-08-31

Playbook §38.5 and §39.12 require training-worker, streaming/high-bandwidth, dynamic-generation and out-of-process capability lifecycles without paper-specific Runtime APIs.

The existing public contracts are sufficient; no new production authority is introduced.

- `runtime.service.api.ServiceLaunchContract` + `ExactServiceRuntimePort` provide one transport-neutral lifecycle ABI for training and streaming services.
- `resource.compute.api.ComputeRequirement` expresses CPU/RAM/GPU count, minimum GPU memory and labels without provider-private state.
- `resource.allocation.api.EndpointAllocationPort.replace_bound` exposes explicit generation-fenced endpoint rebinding.
- `runtime.process.supervision.api` exposes finite command timeout, explicit supervisor deadline/termination and bounded output retention.

`tests/test_runtime_pge_public_contract_v1.py` proves one training worker and one streaming provider can use those same APIs, that service generation changes identity, and that transport/server/SSH placement is absent from the service contract shape.

Existing adversarial coverage supplies the behavior behind that representation:
- `test_resource_endpoint_atomicity_v2.py`: stale/concurrent generation replacement and restart persistence.
- `test_process_supervision_async_v2.py`: late-spawn fencing, timeout cleanup, cancellation tree reap and bounded pipe retention.
- `test_capacity_admission_scheduling_v1.py`: global/lane/hierarchical backpressure.
- `test_service_quiescence_probe_v167.py`: exact quiescence before replacement/retirement.

This is intentionally composition mechanics, not scientific identity. ROLE04 remains owner of capability/Participant/Model identity and ROLE03 remains owner of run/training/evaluation scientific execution identity.