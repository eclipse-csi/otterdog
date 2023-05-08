# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

import json
import os

import pytest


@pytest.fixture
def test_resource_dir():
    return os.path.join(os.path.dirname(os.path.realpath(__file__)), "models/resources")


@pytest.fixture
def github_webhook_data(test_resource_dir):
    filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), test_resource_dir, "github-webhook.json")
    with open(filename, "r") as file:
        return json.load(file)


@pytest.fixture
def otterdog_webhook_data(test_resource_dir):
    filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), test_resource_dir, "otterdog-webhook.json")
    with open(filename, "r") as file:
        return json.load(file)


@pytest.fixture
def github_repo_data(test_resource_dir):
    filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), test_resource_dir, "github-repo.json")
    with open(filename, "r") as file:
        return json.load(file)


@pytest.fixture
def otterdog_repo_data(test_resource_dir):
    filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), test_resource_dir, "otterdog-repo.json")
    with open(filename, "r") as file:
        return json.load(file)


@pytest.fixture
def github_bpr_data(test_resource_dir):
    filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), test_resource_dir, "github-bpr.json")
    with open(filename, "r") as file:
        return json.load(file)


@pytest.fixture
def otterdog_bpr_data(test_resource_dir):
    filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), test_resource_dir, "otterdog-bpr.json")
    with open(filename, "r") as file:
        return json.load(file)