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
from io import StringIO
from typing import Any
from unittest.mock import MagicMock

from otterdog.models import ModelObject
from otterdog.utils import IndentingPrinter, jsonnet_evaluate_snippet, write_patch_object_as_json

_EXAMPLE_CONFIG = "./otterdog/resources/defaults/otterdog-defaults.libsonnet"


def evaluate_generated_jsonnet(model_class: type[ModelObject], template_call: str, **overrides: Any) -> dict[str, Any]:
    """
    Writes the jsonnet of a model object that differs from its template default in the given values,
    like the import operation does, and evaluates it against the template.
    """
    default_data = jsonnet_evaluate_snippet(f"(import '{_EXAMPLE_CONFIG}').{template_call}")
    default_object = model_class.from_model_data(default_data)
    model_object = model_class.from_model_data({**default_data, **overrides})

    output = StringIO()
    write_patch_object_as_json(
        model_object.get_patch_to(default_object),
        IndentingPrinter(output),
        replace_keys=model_object.replace_on_patch_keys(),
    )
    generated = output.getvalue().rstrip().rstrip(",")

    return jsonnet_evaluate_snippet(f"(import '{_EXAMPLE_CONFIG}').{template_call}{generated}")


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
