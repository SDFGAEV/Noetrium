from __future__ import annotations

import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
_WEAK_CONTRACT_PATTERN = re.compile(
    r"Mapping\[str,\s*object\]|\bpayload:\s*object\b|OperationResult\[object\]"
)
_PRIVATE_INITIALIZER_PATTERN = re.compile(
    r'''noetrium_platform\.(?:[^\s"']+\.)?(?:runtime|providers|composition)(?:\.|\b)'''
    r"|\bresearch_platform(?:\.|\b)"
)


def _python_files(base: Path) -> tuple[Path, ...]:
    if not base.exists():
        return ()
    return tuple(
        sorted(
            path for path in base.rglob("*.py")
            if "__pycache__" not in path.parts
        )
    )


def _weak_contract_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for base in (ROOT / "noetrium", ROOT / "noetrium_platform", ROOT / "projects"):
        for path in _python_files(base):
            for line_no, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), 1
            ):
                if _WEAK_CONTRACT_PATTERN.search(line):
                    rows.append(
                        {
                            "path": str(path.relative_to(ROOT)),
                            "line": line_no,
                            "source": line.strip(),
                        }
                    )
    return rows


def _public_initializer_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for path in _python_files(ROOT / "noetrium"):
        if path.name != "__init__.py":
            continue
        for line_no, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), 1
        ):
            if _PRIVATE_INITIALIZER_PATTERN.search(line):
                rows.append(
                    {
                        "path": str(path.relative_to(ROOT)),
                        "line": line_no,
                        "source": line.strip(),
                    }
                )
    return rows


weak_rows = _weak_contract_rows()
initializer_rows = _public_initializer_rows()
document = {
    "public_initializer_violation_count": len(initializer_rows),
    "public_initializer_violations": initializer_rows,
    "rows": weak_rows,
    "weak_contract_count": len(weak_rows),
}
print(json.dumps(document, ensure_ascii=False, sort_keys=True))
raise SystemExit(1 if weak_rows or initializer_rows else 0)
