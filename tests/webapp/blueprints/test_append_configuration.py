#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************


import yaml

from otterdog.webapp.blueprints import BlueprintType, read_blueprint
from otterdog.webapp.blueprints.append_configuration import AppendConfigurationBlueprint

yaml_content = """
id: prevent-force-pushes
name: Prevents force-pushes for the default branch
type: append_configuration
config:
  condition: >-
    $count($.rulesets[allows_force_pushes = false and
    "~DEFAULT_BRANCH" in include_refs and
    "~ALL" in include_repo_names and target = "branch"]) > 0
  content: |-
    {
      # snippet added due to '{{blueprint_url}}'
      rulesets+: [
        orgs.newOrgRuleset('{{blueprint_id}}') {
          allows_creations: true,
          include_repo_names: [
            "~ALL"
          ],
          include_refs: [
            "~DEFAULT_BRANCH"
          ],
          required_pull_request: null,
          required_status_checks: null,
        },
      ],
    }
"""


def test_read():
    config = yaml.safe_load(yaml_content)

    blueprint = read_blueprint("a", config)
    assert blueprint.type == BlueprintType.APPEND_CONFIGURATION

    assert isinstance(blueprint, AppendConfigurationBlueprint)
    assert "\n" not in blueprint.condition
