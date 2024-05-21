#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import pytest

from otterdog.webapp import create_app
from otterdog.webapp.config import config_dict


@pytest.fixture()
def app():
    app = create_app(config_dict["Testing"])

    # other setup can go here

    yield app

    # clean up / reset resources here
