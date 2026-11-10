#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

"""Shared fixtures for credential provider tests that call external command line tools."""

from __future__ import annotations

import json
import os
import stat
import sys
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

# A fake command line tool: it records the arguments it was called with and answers
# with a canned response selected by its first argument (e.g. 'ls', 'show', 'unlock', 'get').
_FAKE_CLI_TEMPLATE = """#!{python} -I
import json
import sys

with open({log!r}, "a") as log:
    log.write(json.dumps(sys.argv[1:]) + "\\n")

with open({responses!r}) as file:
    responses = json.load(file)

command = sys.argv[1] if len(sys.argv) > 1 else ""
response = responses.get(command, {{"status": 2, "stderr": "unexpected command"}})
sys.stdout.write(response.get("stdout", ""))
sys.stderr.write(response.get("stderr", ""))
sys.exit(response.get("status", 0))
"""


class FakeCli:
    def __init__(self, bin_dir: Path, name: str, responses: dict[str, dict[str, Any]]) -> None:
        self._log = bin_dir / f"{name}.log"
        responses_file = bin_dir / f"{name}.json"
        responses_file.write_text(json.dumps(responses))

        executable = bin_dir / name
        executable.write_text(
            _FAKE_CLI_TEMPLATE.format(python=sys.executable, log=str(self._log), responses=str(responses_file))
        )
        executable.chmod(executable.stat().st_mode | stat.S_IXUSR)

    @property
    def invocations(self) -> list[list[str]]:
        if not self._log.exists():
            return []
        return [json.loads(line) for line in self._log.read_text().splitlines()]


@pytest.fixture
def fake_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Callable[[str, dict[str, dict[str, Any]]], FakeCli]:
    """Installs fake command line tools in a directory that takes precedence in PATH."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")

    def _create(name: str, responses: dict[str, dict[str, Any]]) -> FakeCli:
        return FakeCli(bin_dir, name, responses)

    return _create


@pytest.fixture
def empty_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Restricts PATH to an empty directory, simulating a tool that is not installed."""
    empty_dir = tmp_path / "empty-bin"
    empty_dir.mkdir()
    monkeypatch.setenv("PATH", str(empty_dir))


@pytest.fixture(
    params=[
        "$(touch {marker})",
        "`touch {marker}`",
        "x; touch {marker}",
        "x && touch {marker} #",
        "x | touch {marker}",
        "x\ntouch {marker}",
    ],
    ids=["command-substitution", "backticks", "semicolon", "and", "pipe", "newline"],
)
def injection_payload(request: pytest.FixtureRequest, tmp_path: Path) -> tuple[str, Path]:
    """
    A value that would execute 'touch <marker>' if it was ever interpreted by a shell,
    together with the marker file that must not exist after the test.
    """
    marker = tmp_path / "pwned"
    return request.param.format(marker=marker), marker
