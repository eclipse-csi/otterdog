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

    policy = read_policy(config)
    assert policy.type == PolicyType.MACOS_LARGE_RUNNERS_USAGE

    assert isinstance(policy, MacOSLargeRunnersUsagePolicy)
    assert policy.is_workflow_job_permitted([]) is True
    assert policy.is_workflow_job_permitted(["macos-runners-large"]) is False


def test_read_enabled():
    config = yaml.safe_load(enabled)

    policy = read_policy(config)
    assert policy.type == PolicyType.MACOS_LARGE_RUNNERS_USAGE

    assert isinstance(policy, MacOSLargeRunnersUsagePolicy)
    assert policy.is_workflow_job_permitted([]) is True
    assert policy.is_workflow_job_permitted(["macos-runners-large"]) is True


def test_create():
    config = yaml.safe_load(enabled)

    policy = create_policy(PolicyType.MACOS_LARGE_RUNNERS_USAGE, config["config"])

    assert policy.type == PolicyType.MACOS_LARGE_RUNNERS_USAGE

    assert isinstance(policy, MacOSLargeRunnersUsagePolicy)
    assert policy.is_workflow_job_permitted([]) is True
    assert policy.is_workflow_job_permitted(["macos-runners-large"]) is True
