#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import os

import pytest

# Dummy values for settings that decouple/otterdog.webapp.config requires but have no
# built-in default, so the test suite never depends on a developer's local .env file.
os.environ.setdefault("BASE_URL", "http://localhost")
os.environ.setdefault("APP_ROOT", "./approot")
os.environ.setdefault("GITHUB_APP_ID", "dummy-app-id")
os.environ.setdefault("GITHUB_APP_PRIVATE_KEY", "dummy-private-key")
os.environ.setdefault("DEPENDENCY_TRACK_URL", "http://localhost/dependency-track")
os.environ.setdefault("DEPENDENCY_TRACK_TOKEN", "dummy-dependency-track-token")
os.environ.setdefault("OTTERDOG_CONFIG_OWNER", "dummy-owner")
os.environ.setdefault("OTTERDOG_CONFIG_REPO", "dummy-repo")
os.environ.setdefault("OTTERDOG_CONFIG_PATH", "dummy-path")
os.environ.setdefault("OTTERDOG_CONFIG_TOKEN", "dummy-config-token")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "dummy-webhook-secret")

from otterdog.webapp import create_app


@pytest.fixture
def app():
    from otterdog.webapp.config import TestingConfig

    app = create_app(TestingConfig)

    # other setup can go here

    yield app

    # clean up / reset resources here
