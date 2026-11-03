#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import dataclasses
import os
import unittest
from unittest.mock import patch

import jsonschema
import pretend

from otterdog.config import OtterdogConfig
from otterdog.models import FailureType, LivePatchContext
from otterdog.models.github_organization import GitHubOrganization
from otterdog.models.organization_ruleset import OrganizationRuleset
from otterdog.models.repository import Repository
from otterdog.utils import jsonnet_evaluate_file


class GitHubOrganizationTest(unittest.IsolatedAsyncioTestCase):
    TEST_ORG = "test-org"
    BASE_TEMPLATE_URL = "https://github.com/otterdog/test-defaults#test-defaults.libsonnet@main"

    async def asyncSetUp(self):
        base_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "resources")
        otterdog_config_file = os.path.join(base_dir, "otterdog.json")

        self.otterdog_config = OtterdogConfig.from_file(otterdog_config_file, True)
        self.org_config = self.otterdog_config.get_organization_config(self.TEST_ORG)
        self.jsonnet_config = self.org_config.jsonnet_config
        await self.jsonnet_config.init_template()

    def test_load_from_file(self):
        organization = GitHubOrganization.load_from_file(self.TEST_ORG, self.jsonnet_config.org_config_file)

        assert organization.github_id == "test-org"
        assert len(organization.webhooks) == 1
        assert len(organization.repositories) == 2

    def test_load_from_model_ignores_unknown_properties(self):
        data = jsonnet_evaluate_file(self.jsonnet_config.org_config_file)
        data["settings"]["unknown_property_xyz"] = True

        with self.assertLogs("otterdog.models.github_organization", level="WARNING") as log:
            organization = GitHubOrganization.from_model_data(data)

        assert organization.github_id == "test-org"
        assert any("unknown_property_xyz" in message for message in log.output)

    def test_load_from_model_returns_the_unknown_properties(self):
        data = jsonnet_evaluate_file(self.jsonnet_config.org_config_file)
        data["unknown_property_abc"] = True
        data["settings"]["unknown_property_xyz"] = True
        repository = data["repositories"][0]
        repository["has_wikki"] = True

        organization, unknown_properties = GitHubOrganization.from_model_data_with_unknown_properties(data)

        assert organization.github_id == "test-org"
        assert sorted(unknown_properties) == [
            ("", "unknown_property_abc"),
            (f'repositories[name="{repository["name"]}"]', "has_wikki"),
            ("settings", "unknown_property_xyz"),
        ]

    def test_load_from_model_still_rejects_invalid_properties(self):
        data = jsonnet_evaluate_file(self.jsonnet_config.org_config_file)
        data["settings"]["plan"] = 123

        with self.assertRaises(RuntimeError) as context:
            GitHubOrganization.from_model_data(data)

        assert str(context.exception) == "invalid value at 'settings.plan': 123 is not of type 'string'"
        assert isinstance(context.exception.__cause__, jsonschema.exceptions.ValidationError)

    def test_load_from_model_reports_invalid_value_of_any_of_schema(self):
        # 'required_pull_request' is either a pull request or null: the error must
        # name the invalid nested value, not only state that no alternative matched.
        data = jsonnet_evaluate_file(self.jsonnet_config.org_config_file)
        repo = data["repositories"][0]
        repo["rulesets"] = [
            {
                "name": "main",
                "required_pull_request": {"required_approving_review_count": 1, "allowed_merge_methods": "test"},
            }
        ]

        with self.assertRaises(RuntimeError) as context:
            GitHubOrganization.from_model_data(data)

        # the incomplete ruleset reports its missing required properties as well.
        assert (
            f'invalid value at \'repositories[name="{repo["name"]}"].rulesets[name="main"]'
            ".required_pull_request.allowed_merge_methods': 'test' is not of type 'array'"
        ) in str(context.exception).splitlines()

    async def _validate_code_scanning_repository(self, get_repos, aliases=None):
        organization = GitHubOrganization.load_from_file(self.TEST_ORG, self.jsonnet_config.org_config_file)
        repository = organization.repositories[0]
        repository.code_scanning_default_setup_enabled = True
        repository.code_scanning_default_languages = ["python"]
        if aliases is not None:
            repository.aliases = aliases
        get_languages_calls = []

        async def get_languages(_github_id, _repo_name):
            get_languages_calls.append((_github_id, _repo_name))
            return {"Python": 100}

        provider = pretend.stub(
            get_repos=lambda github_id: get_repos(github_id, repository.name),
            rest_api=pretend.stub(repo=pretend.stub(get_languages=get_languages)),
        )
        with patch.object(
            self.jsonnet_config,
            "default_org_config_for_org_id",
            return_value=jsonnet_evaluate_file(self.jsonnet_config.org_config_file),
        ):
            context = await organization.validate(
                self.otterdog_config,
                self.jsonnet_config,
                pretend.stub(is_supported_secret_provider=lambda _provider: False, get_secret=lambda value: value),
                provider,
            )

        return context, repository, get_languages_calls

    async def test_validate_reports_code_scanning_for_missing_repository(self):
        async def get_repos(_github_id, _repository_name):
            return []

        context, _, get_languages_calls = await self._validate_code_scanning_repository(get_repos)

        assert any(
            failure_type == FailureType.ERROR
            and "code_scanning_default_languages" in message
            and "while the repository does not yet exist" in message
            for failure_type, message in context.validation_failures
        )
        assert get_languages_calls == []

    async def test_validate_code_scanning_only_checks_existing_repositories(self):
        async def get_repos(_github_id, repository_name):
            return [repository_name]

        context, repository, get_languages_calls = await self._validate_code_scanning_repository(get_repos)

        assert not context.validation_failures
        assert get_languages_calls == [(self.TEST_ORG, repository.name)]

    async def test_validate_code_scanning_checks_renamed_repository(self):
        async def get_repos(_github_id, _repository_name):
            return ["previous-name"]

        context, repository, get_languages_calls = await self._validate_code_scanning_repository(
            get_repos, aliases=["previous-name"]
        )

        assert not context.validation_failures
        assert get_languages_calls == [(self.TEST_ORG, repository.name)]

    async def test_validate_code_scanning_matches_repository_name_case_insensitively(self):
        async def get_repos(_github_id, repository_name):
            return [repository_name.upper()]

        context, repository, get_languages_calls = await self._validate_code_scanning_repository(get_repos)

        assert not context.validation_failures
        assert get_languages_calls == [(self.TEST_ORG, repository.name)]

    async def test_validate_code_scanning_reports_get_repos_failure(self):
        async def get_repos(_github_id, _repository_name):
            raise RuntimeError("repository lookup failed")

        context, _, get_languages_calls = await self._validate_code_scanning_repository(get_repos)

        assert any(
            failure_type == FailureType.WARNING
            and "could not retrieve repositories" in message
            and "repository lookup failed" in message
            for failure_type, message in context.validation_failures
        )
        assert not any(
            "while the repository does not yet exist" in message for _, message in context.validation_failures
        )
        assert get_languages_calls == []

    def _generate_immutable_releases_settings_changes(self, expected_selected, current_selected, aliases=None):
        expected_org = GitHubOrganization.load_from_file(self.TEST_ORG, self.jsonnet_config.org_config_file)
        current_org = GitHubOrganization.load_from_file(self.TEST_ORG, self.jsonnet_config.org_config_file)

        repository = expected_org.repositories[0]
        repository.aliases = aliases or []

        for org, selected in ((expected_org, expected_selected), (current_org, current_selected)):
            org.settings.immutable_releases_enforced_repositories = "selected"
            org.settings.immutable_releases_selected_repositories = selected(repository.name)

        context = LivePatchContext(
            org_id=self.TEST_ORG,
            repo_filter="",
            update_webhooks=False,
            update_secrets=False,
            update_filter="*",
            current_org_settings=current_org.settings,
            expected_org_settings=expected_org.settings,
        )
        expected_org.generate_live_patch(current_org, context, lambda patch: None)

        # the expected configuration itself must be left untouched
        assert expected_org.settings.immutable_releases_selected_repositories == expected_selected(repository.name)

        return context.modified_org_settings, repository.name

    def test_live_patch_matches_immutable_releases_repositories_case_insensitively(self):
        changes, _ = self._generate_immutable_releases_settings_changes(
            lambda name: [name.upper()],
            lambda name: [name],
        )

        assert "immutable_releases_selected_repositories" not in changes

    def test_live_patch_matches_immutable_releases_repositories_by_alias(self):
        changes, _ = self._generate_immutable_releases_settings_changes(
            lambda name: ["previous-name"],
            lambda name: [name],
            aliases=["previous-name"],
        )

        assert "immutable_releases_selected_repositories" not in changes

    def test_live_patch_ignores_immutable_releases_repositories_selected_several_times(self):
        changes, _ = self._generate_immutable_releases_settings_changes(
            lambda name: [name, name.upper(), "previous-name"],
            lambda name: [name],
            aliases=["previous-name"],
        )

        assert "immutable_releases_selected_repositories" not in changes

    def test_live_patch_reports_added_immutable_releases_repositories(self):
        changes, repository_name = self._generate_immutable_releases_settings_changes(
            lambda name: [name.upper(), "other-repo"],
            lambda name: [name],
        )

        # the configured name of an already selected repository is replaced by the name retrieved from GitHub
        change = changes["immutable_releases_selected_repositories"]
        assert sorted(change.to_value) == sorted([repository_name, "other-repo"])

    def _generate_ruleset_and_repository_patches(
        self, workflow_repository=None, rename=False, existing=False, lift_protection=False
    ):
        expected_org = GitHubOrganization.load_from_file(self.TEST_ORG, self.jsonnet_config.org_config_file)
        current_org = GitHubOrganization.load_from_file(self.TEST_ORG, self.jsonnet_config.org_config_file)

        repository = expected_org.repositories[0]
        if rename:
            expected_org.repositories[0] = dataclasses.replace(repository, name="new-name", aliases=[repository.name])
        else:
            expected_org.add_repository(dataclasses.replace(repository, name="new-name"))

        def ruleset(repository_name, protect_repo_names=True):
            data = {"name": "main", "target": "branch", "protect_repo_names": protect_repo_names}
            if repository_name is not None:
                workflow = f"{self.TEST_ORG}/{repository_name}:.github/workflows/build.yml"
                data["required_workflows"] = {"workflows": [workflow]}
            return OrganizationRuleset.from_model_data(data)

        expected_org.add_ruleset(
            ruleset(workflow_repository and workflow_repository(repository.name), not lift_protection)
        )
        if existing:
            current_org.add_ruleset(ruleset(repository.name))

        context = LivePatchContext(
            org_id=self.TEST_ORG,
            repo_filter="*",
            update_webhooks=False,
            update_secrets=False,
            update_filter="*",
            current_org_settings=current_org.settings,
            expected_org_settings=expected_org.settings,
        )
        patches = []
        expected_org.generate_live_patch(current_org, context, patches.append)
        return patches, repository.name

    @staticmethod
    def _index_of_first_patch(patches, model_type):
        return next(index for index, patch in enumerate(patches) if isinstance(patch.expected_object, model_type))

    def _is_ruleset_applied_before_repositories(self, patches):
        return self._index_of_first_patch(patches, OrganizationRuleset) < self._index_of_first_patch(
            patches, Repository
        )

    def test_live_patch_applies_organization_rulesets_before_repositories(self):
        # e.g. to lift the protection of a repository name before renaming the repository
        patches, _ = self._generate_ruleset_and_repository_patches(rename=True)

        assert self._is_ruleset_applied_before_repositories(patches)

    def test_live_patch_applies_organization_rulesets_requiring_existing_workflows_before_repositories(self):
        patches, _ = self._generate_ruleset_and_repository_patches(lambda name: name.upper())

        assert self._is_ruleset_applied_before_repositories(patches)

    def test_live_patch_resolves_workflows_of_renamed_repositories_by_their_current_name(self):
        # the rename may require to lift the protection of the repository name first
        patches, repository_name = self._generate_ruleset_and_repository_patches(lambda _: "New-Name", rename=True)

        assert self._is_ruleset_applied_before_repositories(patches)
        ruleset_patch = patches[self._index_of_first_patch(patches, OrganizationRuleset)]
        assert ruleset_patch.expected_object.required_workflows.workflows == [
            f"{self.TEST_ORG}/{repository_name}:.github/workflows/build.yml"
        ]

    def test_live_patch_ignores_workflows_of_renamed_repositories(self):
        # GitHub references the repository of a required workflow by its id, which a rename does not change
        patches, _ = self._generate_ruleset_and_repository_patches(lambda _: "new-name", rename=True, existing=True)

        assert not any(isinstance(patch.expected_object, OrganizationRuleset) for patch in patches)

    def test_live_patch_applies_organization_rulesets_requiring_new_workflows_after_repositories(self):
        # a required workflow may reference a repository created by the same apply
        patches, _ = self._generate_ruleset_and_repository_patches(lambda _: "New-Name")

        assert not self._is_ruleset_applied_before_repositories(patches)

    def test_live_patch_splits_organization_rulesets_requiring_new_workflows(self):
        # the other changes are applied before the repositories, e.g. to lift the protection of a repository name
        # before renaming it, with the current workflows
        patches, repository_name = self._generate_ruleset_and_repository_patches(
            lambda _: "New-Name", existing=True, lift_protection=True
        )

        repository_index = self._index_of_first_patch(patches, Repository)
        ruleset_patches = [
            (index < repository_index, set(patch.changes), patch.expected_object.required_workflows.workflows)
            for index, patch in enumerate(patches)
            if isinstance(patch.expected_object, OrganizationRuleset)
        ]
        assert ruleset_patches == [
            (True, {"protect_repo_names"}, [f"{self.TEST_ORG}/{repository_name}:.github/workflows/build.yml"]),
            (False, {"required_workflows"}, [f"{self.TEST_ORG}/New-Name:.github/workflows/build.yml"]),
        ]
