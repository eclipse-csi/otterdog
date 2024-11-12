#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import yaml

from otterdog.webapp.policies import PolicyType, create_policy, read_policy
from otterdog.webapp.policies.macos_large_runners import MacOSLargeRunnersUsagePolicy

disabled = """
name: Limit use of macos larger runners
type: macos_large_runners
config:
  allowed: false
"""

enabled = """
name: Limit use of macos larger runners
type: macos_large_runners
config:
  allowed: true
"""


def test_read_disabled():
    config = yaml.safe_load(disabled)

    policy = read_policy("a", config)
    assert policy.type == PolicyType.MACOS_LARGE_RUNNERS_USAGE

    assert isinstance(policy, MacOSLargeRunnersUsagePolicy)
    assert policy.path == "a"
    assert policy.name == "Limit use of macos larger runners"
    assert policy.description is None
    assert policy._is_workflow_job_permitted([]) == (False, True)
    assert policy._is_workflow_job_permitted(["macos-runners-large"]) == (True, False)


def test_read_enabled():
    config = yaml.safe_load(enabled)

    policy = read_policy("a", config)
    assert policy.type == PolicyType.MACOS_LARGE_RUNNERS_USAGE

    assert isinstance(policy, MacOSLargeRunnersUsagePolicy)
    assert policy.path == "a"
    assert policy.name == "Limit use of macos larger runners"
    assert policy.description is None
    assert policy._is_workflow_job_permitted([]) == (False, True)
    assert policy._is_workflow_job_permitted(["macos-runners-large"]) == (True, True)


def test_create():
    config = yaml.safe_load(enabled)

    policy = create_policy(PolicyType.MACOS_LARGE_RUNNERS_USAGE, "a", "myname", "mydesc", config["config"])

    assert policy.type == PolicyType.MACOS_LARGE_RUNNERS_USAGE

    assert isinstance(policy, MacOSLargeRunnersUsagePolicy)
    assert policy.path == "a"
    assert policy.name == "myname"
    assert policy.description == "mydesc"
    assert policy._is_workflow_job_permitted([]) == (False, True)
    assert policy._is_workflow_job_permitted(["macos-runners-large"]) == (True, True)


def test_merge():
    disabled_config = yaml.safe_load(disabled)
    enabled_config = yaml.safe_load(enabled)

    global_policy = read_policy("global", disabled_config)
    local_policy = read_policy("local", enabled_config)

    merged_policy = global_policy.merge(local_policy)

    assert merged_policy.type == PolicyType.MACOS_LARGE_RUNNERS_USAGE

    assert isinstance(merged_policy, MacOSLargeRunnersUsagePolicy)
    assert merged_policy.path == "local"
    assert merged_policy.name == "Limit use of macos larger runners"
    assert merged_policy.description is None
    assert merged_policy._is_workflow_job_permitted([]) == (False, True)
    assert merged_policy._is_workflow_job_permitted(["macos-runners-large"]) == (True, True)
