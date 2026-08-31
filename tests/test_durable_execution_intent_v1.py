from pathlib import Path
import hashlib

from research_platform.governance.algorithm.api import AlgorithmLanguage, SourceDocument
from research_platform.governance.algorithm.runtime.python_analyzer import PythonAlgorithmAnalyzer

from research_platform.execution.api import ExecutionOperationIntent
from research_platform.execution.command.api import ExecutionCommand
from research_platform.execution.command.providers import SQLiteCommandStore
from research_platform.execution.command.runtime import CommandIntentOwner
from research_platform.execution.operation.api import OperationId
from research_platform.execution.operation.providers import SQLiteOperationStore
from research_platform.execution.operation.runtime import OperationOwner
from research_platform.execution.runtime import ExecutionIntentCoordinator


class _FailOnceOperationSubmission:
    def __init__(self, delegate: OperationOwner) -> None:
        self.delegate = delegate
        self.failed = False

    def submit(self, *args, **kwargs):
        if not self.failed:
            self.failed = True
            raise RuntimeError("injected crash window after durable command")
        return self.delegate.submit(*args, **kwargs)


def _intent() -> ExecutionOperationIntent:
    command = ExecutionCommand.create(
        command_id="cmd:intent:1", command_type="environment.action", payload_schema="action.v1",
        payload_digest="a" * 64, deduplication_key="request:1", now_unix=10.0,
    )
    return ExecutionOperationIntent(command, OperationId("op:intent:1"))


def test_command_then_operation_crash_window_is_replayable(tmp_path: Path):
    command_path = tmp_path / "commands.sqlite3"
    operation_path = tmp_path / "operations.sqlite3"
    commands = CommandIntentOwner(SQLiteCommandStore(command_path))
    operations = OperationOwner(SQLiteOperationStore(operation_path))
    coordinator = ExecutionIntentCoordinator(commands, _FailOnceOperationSubmission(operations))

    try:
        coordinator.submit(_intent())
    except RuntimeError as exc:
        assert "injected crash window" in str(exc)
    else:
        raise AssertionError("fault injection must interrupt between durable authorities")

    assert commands.require(_intent().command.command_id) == _intent().command
    assert SQLiteOperationStore(operation_path).load(_intent().operation_id) is None

    restarted = ExecutionIntentCoordinator(
        CommandIntentOwner(SQLiteCommandStore(command_path)),
        OperationOwner(SQLiteOperationStore(operation_path)),
    )
    recovered = restarted.submit(_intent())
    assert not recovered.command_created
    assert recovered.operation_created
    assert recovered.operation.command_id == recovered.command.command_id
    replayed = restarted.submit(_intent())
    assert not replayed.command_created
    assert not replayed.operation_created
    assert replayed.command == recovered.command
    assert replayed.operation == recovered.operation

def _estimated_complexity(relative_path: str, qualified_name: str) -> str:
    root = Path(__file__).resolve().parents[1]
    text = (root / relative_path).read_text(encoding="utf-8")
    document = SourceDocument(
        relative_path,
        AlgorithmLanguage.PYTHON,
        hashlib.sha256(text.encode("utf-8")).hexdigest(),
        text,
    )
    analysis = PythonAlgorithmAnalyzer().analyze(document)
    symbol = next(row for row in analysis.symbols if row.qualified_name == qualified_name)
    return symbol.metrics.estimated_complexity


def test_fixed_identity_validation_does_not_reintroduce_algorithm_regressions() -> None:
    targets = (
        ("research_platform/execution/api/intent.py", "ExecutionOperationIntent.__post_init__"),
        ("research_platform/execution/operation/api/contracts.py", "OperationSnapshot.__post_init__"),
        ("research_platform/execution/workflow/api/progress.py", "WorkflowOperationBinding.__post_init__"),
        ("research_platform/experimentation/run/manifest/api/evidence.py", "EvidenceBundleManifest.__post_init__"),
    )
    assert {name: _estimated_complexity(path, name) for path, name in targets} == {
        name: "O(1)" for _, name in targets
    }
