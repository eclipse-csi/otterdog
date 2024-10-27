#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import logging

import pytest

from otterdog.providers.github.auth import app_auth
from otterdog.providers.github.rest import RestApi

_logger = logging.getLogger(__name__)

_APP_ID = ""
_APP_PRIVATE_KEY = ""


@pytest.mark.asyncio
@pytest.mark.skipif(not _APP_ID, reason="need to fill in app values")
async def test_list_installations():
    async with RestApi(app_auth(_APP_ID, _APP_PRIVATE_KEY)) as rest_api:
        installations = await rest_api.app.get_app_installations()

        for installation in installations:
            permissions = installation["permissions"]
            if "merge_queues" not in permissions:
                _logger.info(f"{installation['account']['login']} -> missing merge_queue permission")
