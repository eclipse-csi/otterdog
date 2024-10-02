#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import yaml

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


def test_read():
    config = yaml.safe_load(yaml_content)

    policy = read_policy(config)
    assert policy.type == PolicyType.REQUIRED_FILE

    assert isinstance(policy, RequiredFilePolicy)
