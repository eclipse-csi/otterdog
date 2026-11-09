#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import json
from copy import deepcopy
from io import StringIO
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pretend
import pytest

from otterdog.config import OrganizationConfig
from otterdog.credentials import CredentialPlaceHolders
from otterdog.credentials.secret_access_policy import SecretAccessMode, SecretAccessPolicy
from otterdog.jsonnet import JsonnetConfig
from otterdog.models import LivePatchType
from otterdog.models.github_organization import GitHubOrganization
from otterdog.models.team import Team
from otterdog.operations.apply import ApplyOperation
from otterdog.operations.check_status import CheckStatusOperation
from otterdog.operations.local_apply import LocalApplyOperation
from otterdog.operations.local_plan import LocalPlanOperation
from otterdog.operations.plan import PlanOperation
from otterdog.operations.validate import ValidationStatus
from otterdog.utils import UNSET, ExclusionPatterns, IndentingPrinter, LogLevel, unwrap

_BASE_TEMPLATE = "https://github.com/otterdog/test-defaults#test-defaults.libsonnet@main"


def _create_org_config(tmp_path: Path, with_config_files: bool, base_differs: bool = True) -> OrganizationConfig:
    """Create a local-only organization config and, when requested, its desired and BASE files.

    The desired file describes the configuration being planned. The BASE file represents the live
    configuration and can differ in one repository description, giving the operation an observable
    change to report without contacting GitHub.
    """
    jsonnet_config = JsonnetConfig("test-org", str(tmp_path), _BASE_TEMPLATE, local_only=True)
    Path(jsonnet_config.template_file).parent.mkdir(parents=True)
    Path(jsonnet_config.template_file).write_text("{}", encoding="utf-8")

    if with_config_files:
        resource_file = Path(__file__).parents[1] / "models" / "resources" / "otterdogtest.json"
        expected_data = json.loads(resource_file.read_text(encoding="utf-8"))
        expected_data["project_name"] = "test-project"
        expected_data["github_id"] = "test-org"

        current_data = deepcopy(expected_data)
        if base_differs:
            current_data["repositories"][0]["description"] = "changed in GitHub"

        config_file = Path(jsonnet_config.org_config_file)
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text(json.dumps(expected_data), encoding="utf-8")
        Path(f"{config_file}-BASE").write_text(json.dumps(current_data), encoding="utf-8")

    return OrganizationConfig(
        "test-project",
        "test-org",
        ".config",
        _BASE_TEMPLATE,
        jsonnet_config,
        {},
    )


def _initialize_operation(
    operation,
    monkeypatch,
    output: StringIO,
    client,
    current_org=None,
    exclude_teams_pattern=None,
    secret_access_policy=None,
    validation_status: ValidationStatus | None = None,
    mock_validation: bool = True,
):
    """
    Initialize an operation while replacing only GitHub and validation boundaries.
    """
    monkeypatch.setattr(operation, "setup_github_client", lambda org_config: client)
    if mock_validation:
        monkeypatch.setattr(operation, "validate", AsyncMock(return_value=validation_status or ValidationStatus()))
    if current_org is not None:
        monkeypatch.setattr(operation, "load_current_org", AsyncMock(return_value=current_org))

    config = pretend.stub(
        exclude_teams_pattern=exclude_teams_pattern,
        configuration={},
        get_secret_access_policy=lambda org_config: secret_access_policy,
    )
    operation.init(config, IndentingPrinter(output, log_level=LogLevel.ERROR))


async def test_local_plan_reports_changes_for_a_configuration_difference(tmp_path, monkeypatch):
    """
    A local plan reports the difference between the desired and BASE configurations.
    """
    org_config = _create_org_config(tmp_path, with_config_files=True)
    output = StringIO()
    operation = LocalPlanOperation("-BASE", "*", False, False, False, "")
    client = pretend.stub(close=AsyncMock())
    _initialize_operation(operation, monkeypatch, output, client)

    result = await operation.execute(org_config)

    assert result == 0
    assert "1 to change" in output.getvalue()


async def test_local_plan_ignores_differences_of_unmanaged_settings(tmp_path, monkeypatch):
    """
    A setting listed as unmanaged is not compared, the repository description is the only difference.
    """
    org_config = _create_org_config(tmp_path, with_config_files=True)
    org_config.jsonnet_config._unmanaged = frozenset({"repository.description"})
    output = StringIO()
    operation = LocalPlanOperation("-BASE", "*", False, False, False, "")
    client = pretend.stub(close=AsyncMock())
    _initialize_operation(operation, monkeypatch, output, client)

    result = await operation.execute(org_config)

    assert result == 0
    assert "0 to change" in output.getvalue()
    assert "1 to change" not in output.getvalue()


async def test_unmanaged_settings_are_removed_before_loading_the_current_organization(tmp_path, monkeypatch):
    """
    The settings to retrieve also depend on the expected organization, an unmanaged setting must not be in it.
    """
    org_config = _create_org_config(tmp_path, with_config_files=True)
    org_config.jsonnet_config._unmanaged = frozenset({"repository.description"})
    operation = LocalPlanOperation("-BASE", "*", False, False, False, "")
    _initialize_operation(operation, monkeypatch, StringIO(), pretend.stub(close=AsyncMock()))

    descriptions = []
    load_current_org = operation.load_current_org

    async def recording_load_current_org(project_name, github_id, jsonnet_config, expected_org=None):
        descriptions.extend(repository.description for repository in expected_org.repositories)
        return await load_current_org(project_name, github_id, jsonnet_config, expected_org)

    monkeypatch.setattr(operation, "load_current_org", recording_load_current_org)

    await operation.execute(org_config)

    assert descriptions
    assert all(description is UNSET for description in descriptions)


@pytest.mark.parametrize(
    "unmanaged,expected_removals",
    [(frozenset(), "1 to delete"), (frozenset({"repository.secrets"}), "0 to delete")],
)
async def test_local_plan_ignores_unmanaged_resources_of_the_baseline_file(
    tmp_path, monkeypatch, unmanaged, expected_removals
):
    """
    The current organization of a local plan is loaded from a file, its unmanaged resources are not removed.
    """
    org_config = _create_org_config(tmp_path, with_config_files=True, base_differs=False)
    org_config.jsonnet_config._unmanaged = unmanaged

    base_file = Path(f"{org_config.jsonnet_config.org_config_file}-BASE")
    base_data = json.loads(base_file.read_text(encoding="utf-8"))
    base_data["repositories"][0]["secrets"] = [{"name": "TOKEN", "value": "pass:token"}]
    base_file.write_text(json.dumps(base_data), encoding="utf-8")

    output = StringIO()
    operation = LocalPlanOperation("-BASE", "*", False, False, False, "")
    _initialize_operation(operation, monkeypatch, output, pretend.stub(close=AsyncMock()))

    result = await operation.execute(org_config)

    assert result == 0
    assert expected_removals in output.getvalue()


def test_the_github_client_does_not_retrieve_unmanaged_settings_of_created_repositories(tmp_path, monkeypatch):
    org_config = _create_org_config(tmp_path, with_config_files=False)
    org_config.jsonnet_config._unmanaged = frozenset(
        {"repository.topics", "repository.workflows.max_cache_size_gb", "repository.codespaces_secrets"}
    )
    operation = PlanOperation(False, "*", False, False, False, "*")
    monkeypatch.setattr(operation, "get_credentials", lambda *args, **kwargs: None)

    client = operation.setup_github_client(org_config)

    assert client.unmanaged_repository_settings == frozenset({"topics"})


async def test_local_plan_returns_failure_when_the_configuration_is_missing(tmp_path, monkeypatch):
    """
    A local plan returns failure and explains when the desired configuration is absent.
    """
    org_config = _create_org_config(tmp_path, with_config_files=False)
    output = StringIO()
    operation = LocalPlanOperation("-BASE", "*", False, False, False, "")
    client = pretend.stub(close=AsyncMock())
    _initialize_operation(operation, monkeypatch, output, client)

    result = await operation.execute(org_config)

    assert result == 1
    assert "does not yet exist" in output.getvalue()


_TEMPLATE_WITH_DEFAULT_TEAM = """
{
  newOrg(project_name, org_id):: {
    project_name: project_name,
    github_id: org_id,
    settings: {},
    teams: [{ name: "default-project-leads", privacy: "visible" }],
  },
}
"""


_GITHUB_TEAMS = [
    {"name": "default-project-leads", "slug": "default-project-leads"},
    {"name": "my-project-leads", "slug": "my-project-leads"},
    {"name": "Other Project Leads", "slug": "other-project-leads"},
    {"name": "my-team", "slug": "my-team"},
    {"name": "other-team", "slug": "other-team"},
]

_LOCAL_OPERATIONS = pytest.mark.parametrize(
    "create_operation",
    [
        pytest.param(lambda: LocalPlanOperation("-BASE", "*", False, False, False, "", True), id="local-plan"),
        pytest.param(
            lambda: LocalApplyOperation("-BASE", True, True, "*", False, False, False, "", True), id="local-apply"
        ),
    ],
)


async def _diff_teams(tmp_path, monkeypatch, operation, base_teams, expected_teams):
    """
    Runs a local operation between a BASE and a desired configuration that differ in their teams only,
    with the teams matching '.*-project-leads' managed outside otterdog.
    """
    org_config = _create_org_config(tmp_path, with_config_files=True, base_differs=False)
    jsonnet_config = org_config.jsonnet_config
    Path(jsonnet_config.template_file).write_text(_TEMPLATE_WITH_DEFAULT_TEAM, encoding="utf-8")
    for file_name, team_names in (
        (jsonnet_config.org_config_file, expected_teams),
        (f"{jsonnet_config.org_config_file}-BASE", base_teams),
    ):
        config_file = Path(file_name)
        config_data = json.loads(config_file.read_text(encoding="utf-8"))
        config_data["teams"] = [{"name": name, "privacy": "visible"} for name in team_names]
        config_file.write_text(json.dumps(config_data), encoding="utf-8")

    client = pretend.stub(
        close=AsyncMock(),
        get_org_teams=AsyncMock(return_value=_GITHUB_TEAMS),
        add_org_team=AsyncMock(),
        delete_org_team=AsyncMock(),
    )
    results = []
    operation.set_callback(results.append)
    _initialize_operation(
        operation, monkeypatch, StringIO(), client, exclude_teams_pattern=ExclusionPatterns([".*-project-leads"])
    )

    assert await operation.execute(org_config) == 0
    patches = [
        (patch.patch_type, unwrap(patch.expected_object or patch.current_object).name) for patch in results[0].patches
    ]
    return patches, client


@_LOCAL_OPERATIONS
async def test_local_operations_do_not_remove_the_teams_managed_outside_otterdog(
    tmp_path, monkeypatch, create_operation
):
    """
    Like an organization loaded from GitHub, the BASE configuration of a local operation ignores the teams
    whose slug matches the exclusion patterns and that the default configuration does not declare, so removing
    them from the configuration does not delete them. The slug of a team is looked up on GitHub, as a
    configuration only holds its name.
    """
    base_teams = [
        "default-project-leads",
        "my-project-leads",
        # the slug, not the name, matches the exclusion pattern
        "Other Project Leads",
        # not on GitHub, its name is matched instead
        "new-project-leads",
        "my-team",
        "other-team",
    ]

    patches, client = await _diff_teams(
        tmp_path, monkeypatch, create_operation(), base_teams, ["default-project-leads", "my-team"]
    )

    assert patches == [(LivePatchType.REMOVE, "other-team")]
    client.get_org_teams.assert_awaited_once_with("test-org")


@_LOCAL_OPERATIONS
async def test_local_operations_keep_an_unchanged_team_managed_outside_otterdog(
    tmp_path, monkeypatch, create_operation
):
    """
    A team whose slug, but not its name, matches the exclusion patterns passes the validation. When the
    configuration keeps it unchanged, it is not ignored in BASE only, which would plan to add it again.
    """
    teams = ["default-project-leads", "Other Project Leads", "my-team"]

    patches, client = await _diff_teams(tmp_path, monkeypatch, create_operation(), teams, teams)

    assert patches == []
    client.get_org_teams.assert_not_awaited()
    client.add_org_team.assert_not_awaited()


async def test_remove_excluded_teams_does_not_look_up_the_known_slugs(tmp_path):
    """
    The teams loaded from GitHub already have a slug, which is matched without looking it up again.
    """
    org_config = _create_org_config(tmp_path, with_config_files=True)
    jsonnet_config = org_config.jsonnet_config
    Path(jsonnet_config.template_file).write_text(_TEMPLATE_WITH_DEFAULT_TEAM, encoding="utf-8")
    org = GitHubOrganization.from_model_data(jsonnet_config.default_org_config_for_org_id("test-project", "test-org"))
    org.set_teams(
        [
            Team.from_provider_data("test-org", {"name": "Other Project Leads", "slug": "other-project-leads"}),
            Team.from_provider_data("test-org", {"name": "my-team", "slug": "my-team"}),
        ]
    )
    provider = pretend.stub(get_org_teams=AsyncMock())

    await org.remove_excluded_teams(
        "test-project", jsonnet_config, ExclusionPatterns([".*-project-leads"]), provider, None
    )

    assert [team.name for team in org.teams] == ["my-team"]
    provider.get_org_teams.assert_not_awaited()


async def test_apply_reports_no_changes_for_matching_configurations(tmp_path, monkeypatch):
    """
    Apply keeps its user-visible no-op behavior when the desired and live configurations match.
    """
    org_config = _create_org_config(tmp_path, with_config_files=True, base_differs=False)
    expected_org = GitHubOrganization.load_from_file(org_config.github_id, org_config.jsonnet_config.org_config_file)
    output = StringIO()
    operation = ApplyOperation(True, True, "*", False, False, False, "", False)
    client = pretend.stub(close=AsyncMock())
    _initialize_operation(operation, monkeypatch, output, client, expected_org)

    result = await operation.execute(org_config)

    assert result == 0
    assert "No changes required." in output.getvalue()


async def test_apply_processes_a_non_empty_plan(tmp_path, monkeypatch):
    """
    Apply executes the generated patch and reports the completed plan.
    """
    org_config = _create_org_config(tmp_path, with_config_files=True)
    current_org = GitHubOrganization.load_from_file(
        org_config.github_id, f"{org_config.jsonnet_config.org_config_file}-BASE"
    )
    output = StringIO()
    update_repo = AsyncMock()
    operation = ApplyOperation(True, True, "*", False, False, False, "", False)
    client = pretend.stub(
        close=AsyncMock(),
        update_repo=update_repo,
        get_skipped_repository_reason=lambda org_id, repo_name: None,
    )
    _initialize_operation(operation, monkeypatch, output, client, current_org)

    result = await operation.execute(org_config)

    assert result == 0
    assert "Executed plan" in output.getvalue()
    update_repo.assert_awaited_once()


def _org_config_referencing(tmp_path: Path, reference: str) -> tuple[OrganizationConfig, GitHubOrganization]:
    """
    Returns an organization config whose desired configuration adds a repository secret with the given reference to
    a credential provider, never an actual value, and the current organization.
    """
    org_config = _create_org_config(tmp_path, with_config_files=True, base_differs=False)
    config_file = Path(org_config.jsonnet_config.org_config_file)
    current_org = GitHubOrganization.load_from_file(org_config.github_id, f"{config_file}-BASE")
    expected_data = json.loads(config_file.read_text(encoding="utf-8"))
    expected_data["repositories"][0]["secrets"] = [{"name": "TOKEN", "value": reference}]
    config_file.write_text(json.dumps(expected_data), encoding="utf-8")
    return org_config, current_org


def _pass_policy(org_config: OrganizationConfig) -> SecretAccessPolicy:
    return SecretAccessPolicy(
        SecretAccessMode.ENFORCE,
        {"pass": ["bots/{org_name}/**"]},
        CredentialPlaceHolders(org_name=org_config.name, github_id=org_config.github_id),
    )


def _credential_provider(monkeypatch) -> MagicMock:
    credential_provider = MagicMock()
    monkeypatch.setattr(
        "otterdog.config.CredentialProvider.create", lambda provider_type, defaults: credential_provider
    )
    return credential_provider


async def test_apply_never_reads_a_secret_the_organization_is_not_allowed_to_use(tmp_path, monkeypatch):
    """
    Apply aborts before reading from the credential provider a secret outside of the allowed references.
    """
    org_config, current_org = _org_config_referencing(tmp_path, "pass:bots/other-project/token")
    credential_provider = _credential_provider(monkeypatch)
    output = StringIO()
    operation = ApplyOperation(True, True, "*", False, False, False, "", False)
    client = pretend.stub(close=AsyncMock())
    _initialize_operation(
        operation, monkeypatch, output, client, current_org, secret_access_policy=_pass_policy(org_config)
    )

    result = await operation.execute(org_config)

    assert result == 1
    assert "organization 'test-project' is not allowed to reference secret 'pass:bots/other-project/token'" in (
        " ".join(output.getvalue().split())
    )
    credential_provider.get_secret.assert_not_called()


async def test_apply_fails_on_a_secret_rejected_by_the_validation(tmp_path, monkeypatch):
    """
    The validation of otterdog rejects a secret outside of the allowed references, and apply fails without applying
    or resolving anything.
    """
    org_config, current_org = _org_config_referencing(tmp_path, "pass:bots/other-project/token")
    monkeypatch.setattr(
        org_config.jsonnet_config,
        "default_org_config_for_org_id",
        lambda project_name, github_id: {"project_name": project_name, "github_id": github_id, "settings": {}},
    )
    credential_provider = _credential_provider(monkeypatch)
    output = StringIO()
    operation = ApplyOperation(True, True, "*", False, False, False, "", False)
    client = pretend.stub(close=AsyncMock())
    _initialize_operation(
        operation,
        monkeypatch,
        output,
        client,
        current_org,
        secret_access_policy=_pass_policy(org_config),
        mock_validation=False,
    )

    result = await operation.execute(org_config)

    printed = " ".join(output.getvalue().split())
    assert result == 1
    assert "references secret 'pass:bots/other-project/token' that the organization is not allowed to use" in printed
    assert "Planning aborted due to validation errors." in printed
    assert "No changes required." not in printed
    credential_provider.get_secret.assert_not_called()


async def test_a_diff_generated_without_execute_validates_with_the_policy_of_the_organization(tmp_path, monkeypatch):
    """
    push-config and open-pull-request call generate_diff directly, without execute.
    """
    org_config, _ = _org_config_referencing(tmp_path, "pass:bots/other-project/token")
    monkeypatch.setattr(
        org_config.jsonnet_config,
        "default_org_config_for_org_id",
        lambda project_name, github_id: {"project_name": project_name, "github_id": github_id, "settings": {}},
    )
    output = StringIO()
    operation = LocalPlanOperation("-BASE", "*", False, False, False, "")
    client = pretend.stub(close=AsyncMock())
    _initialize_operation(
        operation, monkeypatch, output, client, secret_access_policy=_pass_policy(org_config), mock_validation=False
    )

    result = await operation.generate_diff(org_config)

    assert result == 1
    assert "references secret 'pass:bots/other-project/token' that the organization is not allowed to use" in (
        " ".join(output.getvalue().split())
    )


async def test_apply_fails_when_the_validation_fails(tmp_path, monkeypatch):
    """
    Apply reports validation errors as a failure, not as an organization without changes.
    """
    org_config = _create_org_config(tmp_path, with_config_files=True)
    validation_status = ValidationStatus()
    validation_status.errors = 2
    output = StringIO()
    operation = ApplyOperation(True, True, "*", False, False, False, "", False)
    client = pretend.stub(close=AsyncMock())
    _initialize_operation(operation, monkeypatch, output, client, validation_status=validation_status)

    result = await operation.execute(org_config)

    assert result == 2
    assert "No changes required." not in output.getvalue()


async def test_check_status_reports_the_status_of_matching_configurations(tmp_path, monkeypatch):
    """
    Check-status exposes a valid, in-sync result when the desired and live configurations match.
    """
    org_config = _create_org_config(tmp_path, with_config_files=True, base_differs=False)
    expected_org = GitHubOrganization.load_from_file(org_config.github_id, org_config.jsonnet_config.org_config_file)
    output = StringIO()
    archived_check = AsyncMock(return_value=False)
    client = pretend.stub(
        close=AsyncMock(),
        rest_api=pretend.stub(org=pretend.stub(is_archived=archived_check)),
    )
    operation = CheckStatusOperation(True, "*")
    _initialize_operation(operation, monkeypatch, output, client, expected_org)

    result = await operation.execute(org_config)

    assert result == 0
    assert operation.orgs_status == [
        {
            "org_id": "test-org",
            "is_archived": False,
            "validation_status": {
                "is_valid": True,
                "infos": 0,
                "warnings": 0,
                "errors": 0,
            },
            "sync_status": {
                "in_sync": True,
                "additions": 0,
                "changes": 0,
                "deletions": 0,
            },
        }
    ]
    archived_check.assert_awaited_once_with("test-org")


@pytest.mark.parametrize("delete_resources", [True, False])
def test_apply_plans_with_its_deletion_policy(delete_resources):
    """Repositories are planned with the resources that are deleted, e.g. code security configurations."""
    operation = ApplyOperation(True, True, "*", False, False, False, "", delete_resources)

    assert operation.delete_resources() is delete_resources


def test_plan_does_not_delete_resources():
    assert PlanOperation(True, "*", False, False, False, "").delete_resources() is False


@pytest.mark.parametrize("delete_resources", [True, False])
def test_local_plan_uses_the_deletion_policy_of_the_apply_it_previews(delete_resources):
    operation = LocalPlanOperation("-BASE", "*", False, False, False, "", delete_resources=delete_resources)

    assert operation.delete_resources() is delete_resources
