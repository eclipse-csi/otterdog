# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

import otterdog.organization as org


def test_load(testorg_jsonnet):
    try:
        organization = org.load_from_file("testorg", testorg_jsonnet)
    except Exception as err:
        print(err)
    else:
        print(organization)
