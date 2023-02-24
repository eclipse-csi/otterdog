# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

import jq

import otterdog.mapping as mapping


def test_github_repo_to_otterdog_mapping(github_repo_data):
    otterdog_data = mapping.map_github_repo_data_to_otterdog(github_repo_data)

    assert otterdog_data["secret_scanning"] == "enabled"
    assert otterdog_data["name"] == "otterdog-defaults"


def test_otterdog_repo_to_github_mapping(otterdog_repo_data):
    github_data = mapping.map_otterdog_repo_data_to_github(otterdog_repo_data)

    assert jq.compile(".security_and_analysis.secret_scanning.status")\
             .input(github_data).first() == "enabled"
    assert github_data["name"] == "otterdog-defaults"

    assert "secret_scanning" not in github_data
