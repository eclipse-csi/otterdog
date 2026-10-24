#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

"""Test the values allowed by the schemas, which the models also validate."""

import json
from importlib.resources import files

import pytest

from otterdog import resources
from otterdog.models.github_organization import GitHubOrganization
from otterdog.models.repository import Repository
from otterdog.models.workflow_settings import _FORK_PR_APPROVAL_POLICIES


def _schema(name: str) -> dict:
    return json.loads(files(resources).joinpath(f"schemas/{name}").read_text())


def test_code_scanning_languages_are_the_ones_of_the_model():
    languages = _schema("repository.json")["properties"]["code_scanning_default_languages"]["items"]["enum"]

    assert set(languages) == Repository._valid_code_scanning_languages


def test_fork_pr_approval_policies_are_the_ones_of_the_model():
    policies = _schema("workflow-settings.json")["properties"]["fork_pr_approval_policy"]["enum"]

    assert set(policies) == _FORK_PR_APPROVAL_POLICIES


@pytest.mark.parametrize(
    "repository,message",
    [
        (
            {"code_scanning_default_languages": ["python", "truc"]},
            "invalid value at 'repositories[name=\"my-repo\"].code_scanning_default_languages[1]': 'truc' is not one of",
        ),
        (
            {"merge_commit_title": "TITLE"},
            "invalid value at 'repositories[name=\"my-repo\"].merge_commit_title': 'TITLE' is not one of",
        ),
    ],
    ids=["code_scanning_language", "merge_commit_title"],
)
def test_configuration_with_a_value_that_is_not_allowed_is_rejected(repository, message):
    data = {
        "project_name": "my-project",
        "github_id": "my-org",
        "settings": {},
        "repositories": [{"name": "my-repo", "private": False, **repository}],
    }

    with pytest.raises(RuntimeError) as error:
        GitHubOrganization._validate_org_config(data)

    assert message in str(error.value)
