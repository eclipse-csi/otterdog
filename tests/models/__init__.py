# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

import json
import os
import unittest

from unittest.mock import MagicMock

from abc import ABC, abstractmethod
from typing import Any


class ModelTest(ABC, unittest.TestCase):
    @property
    def org_id(self) -> str:
        return "OtterdogTest"

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
        def get_actor_node_ids(actors):
            return [f"id_{actor[1:]}" for actor in actors]

        def get_app_node_ids(app_names):
            return {app: f"id_{app}" for app in app_names}

        def get_actor_ids_with_type(actors):
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
        with open(filename, "r") as fp:
            return json.load(fp)
