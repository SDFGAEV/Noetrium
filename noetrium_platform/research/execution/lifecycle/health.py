from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from enum import StrEnum
import json
from pathlib import Path

from noetrium_platform.foundation.kernel.kernel import canonical_bytes
from noetrium_platform.foundation.kernel.kernel.durability.durable_file import atomic_replace_bytes
import time

from .contracts import LifecyclePhase


class HealthClassification(StrEnum):
    READY="ready"; STARTING="starting"; STALLED="stalled"; FAILED="failed"; STOPPED="stopped"; UNKNOWN="unknown"


@dataclass(frozen=True, slots=True)
class ResourceHealth:
    rss_bytes: int | None = None
    cpu_percent: float | None = None
    fd_count: int | None = None
    thread_count: int | None = None
    gpu_memory_bytes: int | None = None


@dataclass(frozen=True, slots=True)
class ComponentHealthRecord:
    component_id: str
    phase: LifecyclePhase
    generation: str
    pid: int | None
    process_start_identity: str | None
    heartbeat_interval_s: float | None
    last_heartbeat_at: float | None
    last_progress_at: float | None
    last_failure_id: str | None = None
    resource: ResourceHealth = ResourceHealth()
    updated_at: float = 0.0


@dataclass(frozen=True, slots=True)
class HealthAssessment:
    component_id: str
    classification: HealthClassification
    phase: LifecyclePhase
    heartbeat_age_s: float | None
    progress_age_s: float | None
    last_failure_id: str | None
    reason: str


class ComponentHealthStore:
    """Small authoritative component-health record, atomically replaced by the owning supervisor only."""
    def __init__(self,path:Path)->None: self.path=path
    def write(self,record:ComponentHealthRecord)->None:
        raw=canonical_bytes(record, indent=2)
        atomic_replace_bytes(self.path, raw)
    def read(self)->ComponentHealthRecord:
        data=json.loads(self.path.read_text(encoding="utf-8")); data["phase"]=LifecyclePhase(data["phase"]); data["resource"]=ResourceHealth(**data.get("resource",{})); return ComponentHealthRecord(**data)


class HealthMonitor:
    def __init__(self,*,heartbeat_grace_multiplier:float=3.0,progress_stall_s:float|None=None)->None:
        if heartbeat_grace_multiplier<=1: raise ValueError("heartbeat grace multiplier must exceed 1")
        self.heartbeat_grace_multiplier=heartbeat_grace_multiplier; self.progress_stall_s=progress_stall_s

    def assess(self,record:ComponentHealthRecord,*,now:float|None=None)->HealthAssessment:
        now=time.time() if now is None else now
        hb_age=None if record.last_heartbeat_at is None else max(0.0,now-record.last_heartbeat_at)
        progress_age=None if record.last_progress_at is None else max(0.0,now-record.last_progress_at)
        if record.phase==LifecyclePhase.FAILED:
            return HealthAssessment(record.component_id,HealthClassification.FAILED,record.phase,hb_age,progress_age,record.last_failure_id,"component reported FAILED")
        if record.phase==LifecyclePhase.STOPPED:
            return HealthAssessment(record.component_id,HealthClassification.STOPPED,record.phase,hb_age,progress_age,record.last_failure_id,"component stopped")
        if record.phase==LifecyclePhase.STARTING:
            return HealthAssessment(record.component_id,HealthClassification.STARTING,record.phase,hb_age,progress_age,record.last_failure_id,"component is starting")
        if record.phase!=LifecyclePhase.READY:
            return HealthAssessment(record.component_id,HealthClassification.UNKNOWN,record.phase,hb_age,progress_age,record.last_failure_id,"phase not health-classified")
        if record.heartbeat_interval_s is not None:
            if hb_age is None:
                return HealthAssessment(record.component_id,HealthClassification.STALLED,record.phase,hb_age,progress_age,record.last_failure_id,"READY component has no heartbeat")
            if hb_age>record.heartbeat_interval_s*self.heartbeat_grace_multiplier:
                return HealthAssessment(record.component_id,HealthClassification.STALLED,record.phase,hb_age,progress_age,record.last_failure_id,"heartbeat expired")
        if self.progress_stall_s is not None and progress_age is not None and progress_age>self.progress_stall_s:
            return HealthAssessment(record.component_id,HealthClassification.STALLED,record.phase,hb_age,progress_age,record.last_failure_id,"progress heartbeat expired")
        return HealthAssessment(record.component_id,HealthClassification.READY,record.phase,hb_age,progress_age,record.last_failure_id,"healthy")
