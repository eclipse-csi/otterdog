#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import builtins
import subprocess
import sys

import pytest

from otterdog import __main__ as entry_point
from otterdog import cli


def test_interrupt_while_loading_the_cli(monkeypatch, capsys):
    original_import = builtins.__import__

    def interrupted_import(name, *args, **kwargs):
        if name == "otterdog.cli":
            raise KeyboardInterrupt
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", interrupted_import)

    with pytest.raises(SystemExit) as exit_info:
        entry_point.main()

    assert exit_info.value.code == entry_point.EXIT_CODE_INTERRUPTED
    captured = capsys.readouterr()
    assert captured.err == "\nAborted!\n"
    assert "Traceback" not in captured.err


def test_runs_the_cli(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "cli", lambda: calls.append("cli"))

    entry_point.main()

    assert calls == ["cli"]


def test_entry_point_only_imports_the_standard_library():
    # the interrupt handling only covers the loading of the cli if the entry point itself loads quickly
    script = (
        "import sys, otterdog.__main__; "
        "print(sorted(m for m in sys.modules if m.startswith(('otterdog.', 'click', 'aiohttp', 'rich'))))"
    )
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, check=True)  # noqa: S603

    assert result.stdout.strip() == "['otterdog.__main__']"
