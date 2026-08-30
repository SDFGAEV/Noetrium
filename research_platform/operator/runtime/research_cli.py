from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
from dataclasses import fields, is_dataclass
from enum import Enum
import json
from pathlib import Path
import sys

from research_platform.operator.api import ResearchAction, ResearchFacade, ResearchOperationFailure
from research_platform.platform.kernel.errors import describe_exception

from .application_loader import ResearchApplicationFactorySpec, load_research_application

ResearchCliDelegate = Callable[[list[str] | None], int]
_EXPECTED_ERRORS = (KeyError, ValueError, FileNotFoundError, TypeError, json.JSONDecodeError)


def _plain(value):
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: _plain(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_plain(item) for item in value]
    return value


def _emit(value, *, stream=None) -> None:
    print(
        json.dumps(_plain(value), ensure_ascii=False, sort_keys=True, indent=2),
        file=stream or sys.stdout,
    )


def _add_lifecycle_command(subparsers, action: ResearchAction, help_text: str) -> None:
    parser = subparsers.add_parser(action.value, help=help_text)
    parser.set_defaults(action=action, route="application")
    parser.add_argument("target", help="application-owned target identity")
    payload = parser.add_mutually_exclusive_group()
    payload.add_argument("--payload", help="inline JSON payload")
    payload.add_argument("--payload-file", type=Path, help="UTF-8 JSON payload file")


def build_research_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="research",
        description="Canonical Research Platform product control surface",
    )
    parser.add_argument(
        "--application",
        metavar="MODULE:FACTORY",
        help="explicit application factory for lifecycle commands",
    )
    parser.add_argument("--application-config", type=Path)
    subparsers = parser.add_subparsers(dest="command", required=True)
    _add_lifecycle_command(subparsers, ResearchAction.RUN, "start one application-owned run")
    _add_lifecycle_command(subparsers, ResearchAction.INSPECT, "inspect exact application state")
    _add_lifecycle_command(subparsers, ResearchAction.STOP, "stop one application-owned run")
    _add_lifecycle_command(subparsers, ResearchAction.RESUME, "resume one application-owned run")
    _add_lifecycle_command(
        subparsers,
        ResearchAction.RECONCILE,
        "reconcile one application-owned run from authoritative evidence",
    )
    _add_lifecycle_command(subparsers, ResearchAction.EVIDENCE, "read exact run evidence")
    subparsers.add_parser("diagnose", help="forensic/read-side operator tools")
    subparsers.add_parser("manage", help="platform management and deployment tools")
    return parser


def _load_payload(args: argparse.Namespace):
    if args.payload_file is not None:
        return json.loads(args.payload_file.read_text(encoding="utf-8"))
    if args.payload is not None:
        return json.loads(args.payload)
    return None


def _run_application(args: argparse.Namespace) -> int:
    if not args.application:
        raise ValueError(f"research {args.command} requires --application MODULE:FACTORY")
    spec = ResearchApplicationFactorySpec.parse(args.application)
    application = load_research_application(spec, config_path=args.application_config)
    facade = ResearchFacade(application)
    operation = getattr(facade, args.action.value)
    result = operation(args.target, _load_payload(args))
    _emit({"ok": True, "command": args.command, "result": result})
    return 0


def run_research_cli(
    argv: list[str] | None,
    *,
    diagnose_main: ResearchCliDelegate,
    manage_main: ResearchCliDelegate,
) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    if raw_argv and raw_argv[0] == "diagnose":
        return diagnose_main(raw_argv[1:])
    if raw_argv and raw_argv[0] == "manage":
        return manage_main(raw_argv[1:])
    args = build_research_parser().parse_args(raw_argv)
    try:
        return _run_application(args)
    except ResearchOperationFailure as exc:
        _emit({"ok": False, "command": args.command, "result": exc.result}, stream=sys.stderr)
        return 3
    except _EXPECTED_ERRORS as exc:
        descriptor = describe_exception(exc)
        _emit(
            {
                "ok": False,
                "command": args.command,
                "error_type": descriptor.error_type,
                "error": descriptor.safe_message,
                "error_digest": descriptor.error_digest,
            },
            stream=sys.stderr,
        )
        return 2


__all__ = ["ResearchCliDelegate", "build_research_parser", "run_research_cli"]
