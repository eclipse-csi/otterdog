#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

"""The actions policies of an organization and of its repositories, as part of the organization."""

from importlib.resources import files
from io import StringIO
from typing import Any

import pytest
from pretend import stub

from otterdog.jsonnet import JsonnetConfig
from otterdog.models import LivePatch, LivePatchContext, LivePatchType
from otterdog.models.github_organization import GitHubOrganization
from otterdog.models.organization_actions_policy import OrganizationActionsPolicy
from otterdog.models.repo_actions_policy import RepositoryActionsPolicy
from otterdog.models.repository import Repository
from otterdog.utils import IndentingPrinter, jsonnet_evaluate_snippet

DEFAULTS = files("otterdog").joinpath("resources", "defaults", "otterdog-defaults.libsonnet")

ORG_POLICY = """
  orgs.newOrgActionsPolicy('pinned') {
    include_repo_names: ['~ALL'],
    allowed_events: ['push', 'pull_request', 'workflow_dispatch'],
  }
"""

REPO_POLICY = """
  orgs.newRepoActionsPolicy('release') {
    include_workflows: ['.github/workflows/release.yml'],
    allowed_actors: ['#Maintain'],
  }
"""


def evaluate(expression: str) -> Any:
    return jsonnet_evaluate_snippet(f"local orgs = import '{DEFAULTS}'; {expression}")


def organization(org_policies: str = "", repo_policies: str = "") -> GitHubOrganization:
    return GitHubOrganization.from_model_data(
        evaluate(
            f"""
            orgs.newOrg('my-project', 'my-org') {{
              actions_policies+: [{org_policies}],
              _repositories+:: [
                orgs.newRepo('my-repo') {{
                  actions_policies: [{repo_policies}],
                }},
              ],
            }}
            """
        )
    )


def live_patches(expected: GitHubOrganization, current: GitHubOrganization) -> list[LivePatch]:
    context = LivePatchContext(
        org_id="my-org",
        repo_filter="*",
        update_webhooks=False,
        update_secrets=False,
        update_filter="*",
        current_org_settings=current.settings,
        expected_org_settings=expected.settings,
    )
    patches: list[LivePatch] = []
    expected.generate_live_patch(current, context, patches.append)
    return patches


def test_load_from_model():
    org = organization(ORG_POLICY, REPO_POLICY)

    assert [x.name for x in org.actions_policies] == ["pinned"]
    assert [x.name for x in org.repositories[0].actions_policies] == ["release"]
    assert org.repositories[0].actions_policies[0].allowed_actors == ["#Maintain"]


def test_unknown_property_is_rejected():
    # like the properties of rulesets, a mistyped rule must not be silently ignored
    data = evaluate(f"orgs.newOrg('my-project', 'my-org') {{ actions_policies+: [{ORG_POLICY} {{ unknown: 1 }}] }}")

    with pytest.raises(RuntimeError, match=r"actions_policies\[name=\"pinned\"\].*'unknown' was unexpected"):
        GitHubOrganization.from_model_data(data)


def test_policies_are_part_of_the_model_objects():
    org = organization(ORG_POLICY, REPO_POLICY)

    objects = [(type(x).__name__, type(parent).__name__) for x, parent in org.get_model_objects()]

    assert ("OrganizationActionsPolicy", "NoneType") in objects
    assert ("RepositoryActionsPolicy", "Repository") in objects


def test_new_policies_are_added():
    patches = live_patches(organization(ORG_POLICY, REPO_POLICY), organization())

    added = [(type(x.expected_object), x.patch_type) for x in patches]
    assert (OrganizationActionsPolicy, LivePatchType.ADD) in added
    assert (RepositoryActionsPolicy, LivePatchType.ADD) in added

    repo_patch = next(x for x in patches if isinstance(x.expected_object, RepositoryActionsPolicy))
    assert isinstance(repo_patch.parent_object, Repository)
    assert repo_patch.parent_object.name == "my-repo"


def test_policies_missing_from_the_configuration_are_removed():
    patches = live_patches(organization(), organization(ORG_POLICY, REPO_POLICY))

    assert sorted((type(x.current_object).__name__, x.patch_type.name) for x in patches) == [
        ("OrganizationActionsPolicy", "REMOVE"),
        ("RepositoryActionsPolicy", "REMOVE"),
    ]


def test_organization_policies_are_applied_before_repositories():
    expected = organization(ORG_POLICY)
    expected.add_repository(Repository.from_model_data(evaluate("orgs.newRepo('new-repo')")))

    patches = live_patches(expected, organization())

    types = [type(x.expected_object) for x in patches]
    assert types.index(OrganizationActionsPolicy) < types.index(Repository)


def test_unchanged_policies_have_no_patch():
    assert live_patches(organization(ORG_POLICY, REPO_POLICY), organization(ORG_POLICY, REPO_POLICY)) == []


def test_policies_of_archived_repositories_are_not_changed():
    expected = organization(ORG_POLICY, REPO_POLICY)
    current = organization(ORG_POLICY)
    for org in [expected, current]:
        org.repositories[0].archived = True

    patches = live_patches(expected, current)

    assert not any(isinstance(x.expected_object, RepositoryActionsPolicy) for x in patches)


@pytest.mark.parametrize("policy", [ORG_POLICY, "orgs.newOrgActionsPolicy('all') { allowed_actors: ['@alice'] }"])
def test_import_evaluates_to_the_live_policy(policy: str):
    live = OrganizationActionsPolicy.from_model_data(evaluate(policy))
    default = OrganizationActionsPolicy.from_model_data(evaluate("orgs.newOrgActionsPolicy('default')"))
    jsonnet_config = stub(create_org_actions_policy=JsonnetConfig.create_org_actions_policy)

    output = StringIO()
    live.to_jsonnet(IndentingPrinter(output), jsonnet_config, stub(), False, default)
    jsonnet = output.getvalue().strip().rstrip(",")

    imported = OrganizationActionsPolicy.from_model_data(evaluate(jsonnet))
    assert imported.get_difference_from(live) == {}
