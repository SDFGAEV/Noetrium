from __future__ import annotations

from research_platform.resource.compute.api import ComputeHost, ComputeSchedulerPort
from research_platform.resource.compute.runtime import InMemoryComputeInventory, InMemoryComputeScheduler


def compose_in_memory_compute_scheduler(
    hosts: tuple[ComputeHost, ...],
) -> ComputeSchedulerPort:
    """Assemble the in-memory compute authority behind its public scheduler port."""

    inventory = InMemoryComputeInventory()
    for host in hosts:
        inventory.register_host(host)
    return InMemoryComputeScheduler(inventory)


__all__ = ["compose_in_memory_compute_scheduler"]
