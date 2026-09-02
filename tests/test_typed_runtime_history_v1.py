from noetrium_platform.research.execution.runtime.manager.history import RuntimeHistory
from noetrium_platform.research.execution.runtime.manager.runtime_history_contracts import RuntimeHistoryEntry
from noetrium_platform.research.execution.runtime.manager.runtime_state_contracts import RuntimeControlState, RuntimeTxnPhase
from noetrium_platform.research.execution.runtime.manager.runtime_history_storage import FileRuntimeHistoryStorage


def _state() -> RuntimeControlState:
    return RuntimeControlState(
        "ctl", "manifest", RuntimeTxnPhase.RUNNING, ("verify_release",), None, False,
        ("evidence:1",), None, None, None, 10.0,
    )


def test_runtime_history_semantic_tail_is_typed(tmp_path):
    history = RuntimeHistory(FileRuntimeHistoryStorage(tmp_path / "history.jsonl"))
    entry = history.append(_state())
    assert isinstance(entry, RuntimeHistoryEntry)
    assert entry.state == _state()
    with history.verified_append_session() as session:
        assert isinstance(session.tail, RuntimeHistoryEntry)
        assert session.tail.state.control_id == "ctl"
