#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

"""
Validates the jsonnet examples of the configuration guides.

Every `jsonnet` code block of a guide is a complete organization configuration. It is evaluated
against the example default configuration and validated the same way as `otterdog validate`,
without accessing GitHub.
"""

import re
import shutil
from pathlib import Path

import pretend
import pytest

from otterdog.config import CredentialResolver, OtterdogConfig
from otterdog.models import FailureType
from otterdog.models.github_organization import GitHubOrganization

_ROOT_DIR = Path(__file__).parent.parent
_TEMPLATE_DIR = _ROOT_DIR / "examples" / "template"
_TEMPLATE_URL = "https://github.com/example/otterdog-defaults#otterdog-defaults.libsonnet@main"
_TEMPLATE_IMPORT = "local orgs = import 'vendor/otterdog-defaults/otterdog-defaults.libsonnet';\n\n"

_GUIDE_PAGES = [
    *sorted((_ROOT_DIR / "docs" / "userguide" / "guides").glob("*.md")),
    _ROOT_DIR / "docs" / "operating_otterdog" / "organization-policies.md",
]

# a fenced code block, indented when nested in a content tab or an admonition
_CODE_BLOCK = re.compile(
    r"^(?P<indent>[ ]*)(?P<fence>`{3,})[ ]*(?P<lang>[\w-]*)[^\n]*\n(?P<body>.*?)^(?P=indent)(?P=fence)[ ]*$",
    re.MULTILINE | re.DOTALL,
)
_NEW_ORG = re.compile(r"orgs\.newOrg\('(?P<name>[^']+)'(?:,\s*'(?P<id>[^']+)')?\)")

# languages reported by GitHub for every repository, so that any code scanning language can be configured
_DETECTED_LANGUAGES = {
    "C": 1,
    "C#": 1,
    "Go": 1,
    "Java": 1,
    "JavaScript": 1,
    "Python": 1,
    "Ruby": 1,
    "Rust": 1,
    "Swift": 1,
}


def _jsonnet_examples() -> list:
    examples = []
    for page in _GUIDE_PAGES:
        blocks = [m for m in _CODE_BLOCK.finditer(page.read_text()) if m.group("lang") == "jsonnet"]
        for index, match in enumerate(blocks, start=1):
            indent = len(match.group("indent"))
            body = "".join(line[indent:] for line in match.group("body").splitlines(keepends=True))
            examples.append(pytest.param(body, id=f"{page.stem}-{index}"))
    return examples


def _validation_provider(organization: GitHubOrganization):
    members = [{"login": member} for team in organization.teams for member in team.members]
    repo_names = [repo.name for repo in organization.repositories]

    async def list_members(_github_id):
        return members

    async def get_repos(_github_id):
        return repo_names

    async def get_languages(_github_id, _repo_name):
        return _DETECTED_LANGUAGES

    return pretend.stub(
        get_repos=get_repos,
        rest_api=pretend.stub(
            org=pretend.stub(list_members=list_members),
            repo=pretend.stub(get_languages=get_languages),
        ),
    )


def test_guides_contain_examples():
    assert all(page.exists() for page in _GUIDE_PAGES)
    assert len(_jsonnet_examples()) > 0


@pytest.mark.parametrize("example", _jsonnet_examples())
async def test_guide_example_is_valid(example: str, tmp_path: Path):
    match = _NEW_ORG.search(example)
    assert match is not None, "a guide example must be a complete organization configuration using 'orgs.newOrg'"
    github_id = match.group("id") or match.group("name")

    org_dir = tmp_path / github_id
    shutil.copytree(_TEMPLATE_DIR, org_dir / "vendor" / "otterdog-defaults")
    content = example if "import " in example else _TEMPLATE_IMPORT + example
    (org_dir / f"{github_id}.jsonnet").write_text(content)

    config = OtterdogConfig.from_dict(
        {
            "defaults": {"jsonnet": {"base_template": _TEMPLATE_URL, "config_dir": "."}},
            "organizations": [{"name": match.group("name"), "github_id": github_id}],
        },
        True,
        str(tmp_path),
    )
    jsonnet_config = config.get_organization_config(github_id).jsonnet_config
    await jsonnet_config.init_template()

    organization = GitHubOrganization.load_from_file(github_id, jsonnet_config.org_config_file)
    context = await organization.validate(
        config,
        jsonnet_config,
        CredentialResolver(config),
        _validation_provider(organization),
    )

    failures = [
        f"{failure_type.name}: {message}"
        for failure_type, message in context.validation_failures
        if failure_type in (FailureType.WARNING, FailureType.ERROR)
    ]
    assert failures == []
