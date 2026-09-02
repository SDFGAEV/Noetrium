from __future__ import annotations

from noetrium_platform.infrastructure.lifecycle.session.runtime.tmux_parser import parse_tmux_snapshot


def test_parser_accepts_literal_tmux_30a_format_escape() -> None:
    snapshot = parse_tmux_snapshot(
        "research-platform-shell",
        "research-platform-shell\\t123\\t0\\texec /usr/bin/bash -il\\t/data/research-platform\n"
    )
    assert snapshot.session_name == "research-platform-shell"
    assert snapshot.controller_pid == 123
    assert snapshot.controller_dead is False
    assert snapshot.current_path == "/data/research-platform"


def test_parser_accepts_actual_tab_format() -> None:
    snapshot = parse_tmux_snapshot(
        "research-platform-shell",
        "research-platform-shell\t123\t0\texec /usr/bin/bash -il\t/data/research-platform\n"
    )
    assert snapshot.start_command == "exec /usr/bin/bash -il"
