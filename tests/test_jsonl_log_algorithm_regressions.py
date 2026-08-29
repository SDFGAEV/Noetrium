from __future__ import annotations

import json
from pathlib import Path

import pytest

from research_platform.observability.logging.context.api import DiagnosticAddress
from research_platform.observability.logging.record.api import LogLevel, LogRecord
from research_platform.observability.logging.storage.runtime.jsonl import (
    JsonlLogCorruptionError,
    JsonlLogStore as RuntimeJsonlLogStore,
)
from tests._concurrency_support import jsonl_log_store as JsonlLogStore
from research_platform.observability.logging.storage.composition import build_jsonl_log_store
from research_platform.platform.concurrency.composition import build_concurrency_runtime
from research_platform.scope.api import PLATFORM_SCOPE


def _record(index: int) -> LogRecord:
    return LogRecord(
        f"log-{index}",
        float(index),
        LogLevel.INFO,
        "test",
        "event",
        "safe",
        DiagnosticAddress((PLATFORM_SCOPE,)),
    )


def test_jsonl_store_uses_structural_logging_ports_without_nominal_bases() -> None:
    from research_platform.observability.logging.query.api import LogQueryPort
    from research_platform.observability.logging.sink.api import LogSinkPort

    assert LogQueryPort not in RuntimeJsonlLogStore.__mro__
    assert LogSinkPort not in RuntimeJsonlLogStore.__mro__
    assert callable(RuntimeJsonlLogStore.append)
    assert callable(RuntimeJsonlLogStore.query)


def test_query_retries_windows_snapshot_permission_race(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import os

    if os.name != "nt":
        pytest.skip("Windows transient permission race")
    store = JsonlLogStore(tmp_path / "events.jsonl")
    store.append(_record(1))
    original = RuntimeJsonlLogStore._iter_frozen_lines
    attempts = {"count": 0}

    def flaky(snapshot):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise PermissionError(13, "simulated rotation permission race")
        yield from original(snapshot)

    monkeypatch.setattr(RuntimeJsonlLogStore, "_iter_frozen_lines", staticmethod(flaky))
    assert [row.log_id for row in store.query(limit=10)] == ["log-1"]
    assert attempts["count"] == 2


def test_query_persistent_windows_permission_failure_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import os

    if os.name != "nt":
        pytest.skip("Windows transient permission race")
    store = JsonlLogStore(tmp_path / "events.jsonl")
    store.append(_record(1))
    attempts = {"count": 0}

    def denied(snapshot):
        del snapshot
        attempts["count"] += 1
        raise PermissionError(13, "persistent permission failure")
        yield

    monkeypatch.setattr(RuntimeJsonlLogStore, "_iter_frozen_lines", staticmethod(denied))
    with pytest.raises(RuntimeError, match="stable segment generation") as exc_info:
        store.query(limit=10)
    assert isinstance(exc_info.value.__cause__, PermissionError)
    assert attempts["count"] == 4


def test_store_keeps_logical_path_identity_if_live_leaf_resolution_drifts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "events.jsonl"
    rival = tmp_path / "events.jsonl.1"
    original_resolve = Path.resolve

    def drifting_resolve(candidate: Path, *args, **kwargs):
        if candidate == path:
            return rival
        return original_resolve(candidate, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", drifting_resolve)
    runtime = build_concurrency_runtime()
    group = runtime.open_task_group("jsonl-logical-path-regression")
    try:
        store = build_jsonl_log_store(path, task_group=group, max_bytes=700, max_segments=8)
        assert store.path == path
        assert store._guard_path == path.with_name("events.jsonl.guard.lock")
        store.append(_record(1))
        assert path.is_file()
        assert not rival.exists()
    finally:
        runtime.close()


def test_query_limit_returns_globally_newest_records_without_rotation(tmp_path: Path) -> None:
    store = JsonlLogStore(tmp_path / "events.jsonl")
    for index in range(5):
        store.append(_record(index))
    assert [row.log_id for row in store.query(limit=3)] == ["log-4", "log-3", "log-2"]


def test_query_limit_returns_globally_newest_records_across_segments(tmp_path: Path) -> None:
    store = JsonlLogStore(tmp_path / "events.jsonl", max_bytes=1, max_segments=4)
    for index in range(5):
        store.append(_record(index))
    assert [row.log_id for row in store.query(limit=3)] == ["log-4", "log-3", "log-2"]
    assert (tmp_path / "events.jsonl.4").exists()


def test_wrong_schema_is_corruption_not_silently_decoded(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    store = JsonlLogStore(path)
    store.append(_record(1))
    row = json.loads(path.read_text(encoding="utf-8"))
    row["schema_version"] = "wrong.schema"
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    with pytest.raises(JsonlLogCorruptionError):
        store.query()


def test_wrong_persisted_scalar_types_are_corruption_not_coerced(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    store = JsonlLogStore(path)
    store.append(_record(1))
    row = json.loads(path.read_text(encoding="utf-8"))
    row["log_id"] = 123
    row["correlation_refs"] = [99]
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    with pytest.raises(JsonlLogCorruptionError):
        store.query()


def test_wrong_persisted_attribute_shape_is_typed_corruption(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    store = JsonlLogStore(path)
    store.append(_record(1))
    row = json.loads(path.read_text(encoding="utf-8"))
    row["attributes"] = ["a"]
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    with pytest.raises(JsonlLogCorruptionError):
        store.query()


def test_log_record_rejects_non_finite_timestamp_before_persistence() -> None:
    with pytest.raises(ValueError, match="finite"):
        LogRecord(
            "log-nan",
            float("nan"),
            LogLevel.INFO,
            "test",
            "event",
            "safe",
            DiagnosticAddress((PLATFORM_SCOPE,)),
        )


def test_duplicate_json_object_keys_are_complete_line_corruption(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    store = JsonlLogStore(path)
    store.append(_record(1))
    line = path.read_text(encoding="utf-8")
    line = line.replace('"log_id":"log-1"', '"log_id":"log-1","log_id":"log-1"', 1)
    path.write_text(line, encoding="utf-8")
    with pytest.raises(JsonlLogCorruptionError):
        store.query()


def test_jsonl_storage_uses_single_byte_newlines_for_byte_precise_rotation(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    store = JsonlLogStore(path)
    store.append(_record(1))
    raw = path.read_bytes()
    assert raw.endswith(b"\n")
    assert not raw.endswith(b"\r\n")


def _append_worker(path: str, worker: int, count: int) -> None:
    runtime = build_concurrency_runtime()
    group = runtime.open_task_group(f"multiprocess-log-writer:{worker}")
    store = build_jsonl_log_store(path, task_group=group, max_bytes=700, max_segments=64)
    try:
        for offset in range(count):
            index = worker * 1000 + offset
            store.append(_record(index))
    finally:
        runtime.close()


def test_multiple_processes_append_and_rotate_without_overwrite(tmp_path: Path) -> None:
    import multiprocessing

    path = tmp_path / "events.jsonl"
    context = multiprocessing.get_context("spawn")
    processes = [context.Process(target=_append_worker, args=(str(path), worker, 12)) for worker in range(4)]
    for process in processes:
        process.start()
    for process in processes:
        process.join(30)
        assert process.exitcode == 0
    rows = JsonlLogStore(path, max_bytes=700, max_segments=64).query(limit=1000)
    assert len(rows) == 48
    assert len({row.log_id for row in rows}) == 48


def _query_worker(path: str, stop) -> None:
    runtime = build_concurrency_runtime()
    group = runtime.open_task_group("multiprocess-log-reader")
    store = build_jsonl_log_store(path, task_group=group, max_bytes=700, max_segments=64)
    try:
        while not stop.wait(0.001):
            rows = store.query(limit=1000)
            ids = [row.log_id for row in rows]
            if len(ids) != len(set(ids)):
                raise AssertionError("concurrent JSONL query returned duplicate log identities")
    finally:
        runtime.close()


def test_multiple_processes_rotate_while_concurrent_readers_query(tmp_path: Path) -> None:
    import multiprocessing

    path = tmp_path / "events.jsonl"
    context = multiprocessing.get_context("spawn")
    stop = context.Event()
    readers = [
        context.Process(target=_query_worker, args=(str(path), stop)) for _ in range(2)
    ]
    writers = [
        context.Process(target=_append_worker, args=(str(path), worker, 12))
        for worker in range(4)
    ]
    for process in readers + writers:
        process.start()
    for process in writers:
        process.join(30)
        assert process.exitcode == 0
    stop.set()
    for process in readers:
        process.join(30)
        assert process.exitcode == 0
    rows = JsonlLogStore(path, max_bytes=700, max_segments=64).query(limit=1000)
    assert len(rows) == 48
    assert len({row.log_id for row in rows}) == 48
