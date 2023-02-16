#  *******************************************************************************
#  Copyright (c) 2023 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the MIT License
#  which is available at https://spdx.org/licenses/MIT.html
#  SPDX-License-Identifier: MIT
#  *******************************************************************************

import os

import pytest


@pytest.fixture
def testorg_jsonnet():
    return os.path.join(os.path.dirname(os.path.realpath(__file__)), "resources/testorg.jsonnet")


@pytest.fixture()
def test_resource_dir():
    return os.path.join(os.path.dirname(os.path.realpath(__file__)), "resources")
