from collections.abc import Mapping
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

import pretend
import pytest

from otterdog import utils
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


@pytest.fixture()
def deterministic_days_since():
    fixed_now = datetime(2025, 1, 1, tzinfo=UTC)

    def days_since_wrapper(iso_date_str: str, _now: datetime) -> str:
        return utils.days_since(iso_date_str, fixed_now)

    return days_since_wrapper


class MockWebClient:
    @asynccontextmanager
    async def get_logged_in_page(self):
        """Noop context manager."""
        yield

    def setup_newest_comment_date(self, iso_date_str):
        """Enable WebClient get_security_advisory_newest_comment_date"""

        async def mock(ghsa_link, page):
            return iso_date_str

        self.get_security_advisory_newest_comment_date = mock


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
        self.web_client = MockWebClient()

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
