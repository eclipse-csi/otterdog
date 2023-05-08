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

from abc import ABC, abstractmethod
from typing import Any


class ModelTest(ABC, unittest.TestCase):
    @abstractmethod
    def model_data(self):
        pass

    @property
    @abstractmethod
    def provider_data(self):
        pass

    def load_json_resource(self, file: str) -> dict[str, Any]:
        filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), f"resources/{file}")
        with open(filename, "r") as file:
            return json.load(file)
