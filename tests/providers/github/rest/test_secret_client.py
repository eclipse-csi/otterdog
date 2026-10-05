#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from otterdog.providers.github.rest.secret_client import SecretClient, SecretScope


def test_environment_secret_path_url_encodes_environment_name() -> None:
    """A slash in an environment name must stay inside its URL path segment."""
    path = SecretClient._path(SecretScope.ENVIRONMENT, "org", "repo", "release/candidate")

    assert path == "/repos/org/repo/environments/release%2Fcandidate/secrets"
