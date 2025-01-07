#  *******************************************************************************
#  Copyright (c) 2023-2025 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import json
import os
import unittest
from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any
from unittest.mock import MagicMock

from otterdog.models import ModelObject
from otterdog.utils import jsonnet_evaluate_snippet

_EXAMPLE_CONFIG = "./examples/template/otterdog-defaults.libsonnet"


class ModelTest(ABC, unittest.IsolatedAsyncioTestCase):
    @property
    def org_id(self) -> str:
        return "OtterdogTest"

    @property
    @abstractmethod
    def template_function(self) -> str:
        pass

    @abstractmethod
    def create_model(self, data: Mapping[str, Any]) -> ModelObject:
        pass

    @property
    @abstractmethod
    def model_data(self):
        pass

    @property
    @abstractmethod
    def provider_data(self):
        pass

    @property
    def provider(self):
        async def get_actor_node_ids(actors):
            return [f"id_{actor[1:]}" for actor in actors]

        async def get_app_node_ids(app_names):
            return {app: f"id_{app}" for app in app_names}

        async def get_actor_ids_with_type(actors):
            result = []
            for actor in actors:
                if "/" in actor:
                    result.append(("Team", (f"id_{actor[1:]}", f"id_{actor[1:]}")))
                else:
                    result.append(("User", (f"id_{actor[1:]}", f"id_{actor[1:]}")))
            return result

        provider = MagicMock()

        provider.get_actor_node_ids = MagicMock(side_effect=get_actor_node_ids)
        provider.get_app_node_ids = MagicMock(side_effect=get_app_node_ids)
        provider.get_actor_ids_with_type = MagicMock(side_effect=get_actor_ids_with_type)

        return provider

    @staticmethod
    def load_json_resource(file: str) -> dict[str, Any]:
        filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), f"resources/{file}")
        with open(filename) as fp:
            return json.load(fp)

    def test_example_config(self) -> None:
        snippet = f"(import '{_EXAMPLE_CONFIG}').{self.template_function}('default')"
        json_data = jsonnet_evaluate_snippet(snippet)

        model_object = self.create_model(json_data)
        assert model_object is not None
        if model_object.is_keyed():
            assert model_object.get_key_value() == "default"
