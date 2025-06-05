from collections.abc import Mapping
from typing import Any

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
