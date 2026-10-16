#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from importlib.resources import files

from otterdog.utils import jsonnet_evaluate_snippet


def test_packaged_defaults_evaluate_with_their_sibling_helper():
    """Packaged defaults must resolve the adjacent helper used to produce the repositories list."""
    defaults = files("otterdog").joinpath("resources", "defaults", "otterdog-defaults.libsonnet")

    organization = jsonnet_evaluate_snippet(f"(import '{defaults}').newOrg('sample', 'sample')")

    assert organization["github_id"] == "sample"
    assert organization["repositories"] == []
