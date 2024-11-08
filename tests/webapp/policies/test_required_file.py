#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from dataclasses import fields
from unittest import mock

import yaml

from otterdog.models.repository import Repository
from otterdog.webapp.policies import PolicyType, read_policy
from otterdog.webapp.policies.required_file import RequiredFilePolicy

yaml_content = """
name: Requires SECURITY.md file
type: required_file
config:
  files:
    - path: SECURITY.md
      repo_selector:
        name_pattern: .github
      content: |
        This is our security policy.
        Please head over to....
"""

multiple_repo_selection = """
name: Require file
type: required_file
config:
    files:
      - path: .github/workflows/dependabot-auto-merge.yml
        repo_selector:
          name_pattern:
            - .github
            - repo-1
            - repo-2
            - repo-3
        content: |
          name: Dependabot auto-merge
          on: pull_request_target
          permissions: read-all
          jobs:
            dependabot:
              permissions:
                contents: write
                pull-requests: write
              uses: adoptium/.github/.github/workflows/dependabot-auto-merge.yml@main
"""


def test_read():
    config = yaml.safe_load(yaml_content)

    policy = read_policy("a", config)
    assert policy.type == PolicyType.REQUIRED_FILE

    assert isinstance(policy, RequiredFilePolicy)


def test_repo_selector_multiple_repos():
    config = yaml.safe_load(multiple_repo_selection)

    policy = read_policy("a", config)
    assert policy.type == PolicyType.REQUIRED_FILE

    assert isinstance(policy, RequiredFilePolicy)
    assert len(policy.files) == 1

    required_file = policy.files[0]

    assert required_file.strict is False

    selector = required_file.repo_selector

    assert selector.matches(create_repo_with_name(".github"))
    assert selector.matches(create_repo_with_name("repo-1"))
    assert selector.matches(create_repo_with_name("repo-10")) is False


def create_repo_with_name(name: str) -> Repository:
    repo = create_dataclass_mock(Repository)
    repo.name = name
    return repo


def create_dataclass_mock(obj):
    return mock.Mock(spec_set=[field.name for field in fields(obj)])
