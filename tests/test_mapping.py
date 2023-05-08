# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

import jq

import otterdog.mapping as mapping


def test_otterdog_webhook_to_github_mapping(otterdog_webhook_data):
    github_data = mapping.map_otterdog_org_webhook_data_to_github(otterdog_webhook_data)

    assert jq.compile(".config.secret").input(github_data).first() == "blabla"
    assert jq.compile(".config.url").input(github_data).first() == "https://www.example.org"
    assert jq.compile(".config.insecure_ssl").input(github_data).first() == "0"
    assert jq.compile(".config.content_type").input(github_data).first() == "form"

    assert "url" not in github_data


def test_otterdog_repo_to_github_mapping(otterdog_repo_data):
    github_data = mapping.map_otterdog_repo_data_to_github(otterdog_repo_data)

    assert jq.compile(".security_and_analysis.secret_scanning.status")\
             .input(github_data).first() == "enabled"
    assert github_data["name"] == "otterdog-defaults"

    assert "secret_scanning" not in github_data
