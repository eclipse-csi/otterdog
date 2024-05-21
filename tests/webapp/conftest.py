#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import pytest

from otterdog.webapp import create_app


@pytest.fixture()
def app():
    from otterdog.webapp.config import TestingConfig

    app = create_app(TestingConfig)

    # other setup can go here

    yield app

    # clean up / reset resources here
