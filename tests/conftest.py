from collections.abc import Mapping
from typing import Any

import pretend
import pytest

from otterdog.jsonnet import JsonnetConfig
from otterdog.models import ModelObject
from otterdog.models.repository import Repository
from tests.models import ModelTest


@pytest.fixture()
def repository_test():
    class RepositoryTest(ModelTest):
        def create_model(self, data: Mapping[str, Any]) -> ModelObject:
            return Repository.from_model_data(data)

        @property
        def template_function(self) -> str:
            return JsonnetConfig.create_repo

        @property
        def model_data(self):
            return self.load_json_resource("otterdog-repo.json")

        @property
        def provider_data(self):
            return self.load_json_resource("github-repo.json")

    return RepositoryTest()


class MockGitHubProvider:
    def __init__(self):
        self.rest_api = pretend.stub(
            org=pretend.stub(),
            repo=pretend.stub(),
            team=pretend.stub(),
            user=pretend.stub(),
            app=pretend.stub(),
        )
        self.graphql = pretend.stub()
        self.web = pretend.stub()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    #
    #  Additional setup methods for other API calls can be added here
    #
    def setup_org_advisories(self, advisories_by_state):
        async def mock_get_security_advisories(github_id, state):
            return advisories_by_state.get(state, [])

        self.rest_api.org.get_security_advisories = mock_get_security_advisories
        return self


@pytest.fixture()
def mock_github_provider():
    """Fixture that provides a configurable mock GitHub provider.

    We can set up various mock responses  for different API methods.

    Usage examples:
        # Basic usage with advisories
        mock_provider = mock_github_provider()
        mock_provider.setup_org_advisories({"published": [advisory1, advisory2]})
    """
    return MockGitHubProvider


# Load `github` fixture
pytest_plugins = ["tests.providers.github.github_provider_mock"]
