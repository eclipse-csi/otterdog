#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import os
import unittest
from unittest.mock import patch

import jsonschema
import pretend

from otterdog.config import OtterdogConfig
from otterdog.models import FailureType
from otterdog.models.github_organization import GitHubOrganization
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

    def test_load_from_model_still_rejects_invalid_properties(self):
        data = jsonnet_evaluate_file(self.jsonnet_config.org_config_file)
        data["settings"]["plan"] = 123

        with self.assertRaises(jsonschema.exceptions.ValidationError):
            GitHubOrganization.from_model_data(data)

    async def _validate_code_scanning_repository(self, get_repos):
        organization = GitHubOrganization.load_from_file(self.TEST_ORG, self.jsonnet_config.org_config_file)
        repository = organization.repositories[0]
        repository.code_scanning_default_setup_enabled = True
        repository.code_scanning_default_languages = ["python"]
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
