#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from importlib.resources import files
from io import StringIO

import pytest
from pretend import stub

from otterdog.jsonnet import JsonnetConfig
from otterdog.operations.show_default import ShowDefaultOperation
from otterdog.utils import IndentingPrinter, LogLevel

ORG_ID = "OtterdogTest"
SECRET_SECTIONS = [
    "Organization Dependabot Secret",
    "Organization Codespaces Secret",
    "Repository Dependabot Secret",
    "Repository Codespaces Secret",
]
SECRET_FUNCTIONS = [
    "newOrgDependabotSecret",
    "newOrgCodespacesSecret",
    "newRepoDependabotSecret",
    "newRepoCodespacesSecret",
]


def write_template(tmp_path, excluded_functions):
    """Writes the packaged default configuration to the vendor directory, without the excluded functions."""
    defaults = files("otterdog").joinpath("resources", "defaults", "otterdog-defaults.libsonnet")
    template_dir = tmp_path / ORG_ID / "vendor" / "otterdog-defaults"
    template_dir.mkdir(parents=True)
    (template_dir / "otterdog-defaults.libsonnet").write_text(
        f"local defaults = import '{defaults}';\n"
        "{\n"
        "  [name]: defaults[name]\n"
        "  for name in std.objectFieldsAll(defaults)\n"
        f"  if !std.member({excluded_functions!r}, name)\n"
        "}\n"
    )


async def show_default(tmp_path) -> str:
    jsonnet_config = JsonnetConfig(
        ORG_ID,
        str(tmp_path),
        "https://github.com/example/otterdog-defaults#otterdog-defaults.libsonnet@main",
        True,
    )
    output = StringIO()
    operation = ShowDefaultOperation(markdown=True)
    operation.init(None, IndentingPrinter(output, log_level=LogLevel.ERROR))  # type: ignore

    assert await operation.execute(stub(jsonnet_config=jsonnet_config)) == 0  # type: ignore
    return output.getvalue()


async def test_secret_defaults_are_shown(tmp_path):
    write_template(tmp_path, [])

    output = await show_default(tmp_path)

    for section in SECRET_SECTIONS:
        assert f'=== "{section}"' in output


@pytest.mark.parametrize("excluded_function", SECRET_FUNCTIONS)
async def test_secret_defaults_missing_from_the_template_are_skipped(tmp_path, excluded_function):
    write_template(tmp_path, [excluded_function])

    output = await show_default(tmp_path)

    shown = [section for section in SECRET_SECTIONS if f'=== "{section}"' in output]
    assert shown == [s for s, f in zip(SECRET_SECTIONS, SECRET_FUNCTIONS, strict=True) if f != excluded_function]
    assert '=== "Repository Variable"' in output
