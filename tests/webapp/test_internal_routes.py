#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from unittest import mock

from otterdog.webapp.internal import routes


async def test_init_forces_the_refresh_of_every_installation(app, monkeypatch):
    """
    Exercised through a request context rather than a test client.

    Booting the app would run its startup hooks, which expect a running mongodb.
    """

    update_installations_from_config = mock.AsyncMock()

    monkeypatch.setattr(routes, "refresh_otterdog_config", mock.AsyncMock(return_value="config"))
    monkeypatch.setattr(routes, "refresh_global_policies", mock.AsyncMock(return_value=["policy"]))
    monkeypatch.setattr(routes, "refresh_global_blueprints", mock.AsyncMock(return_value=["blueprint"]))
    monkeypatch.setattr(routes, "update_installations_from_config", update_installations_from_config)
    monkeypatch.setattr(app, "add_background_task", mock.MagicMock())

    async with app.test_request_context("/internal/init"):
        _, status = await routes.init()

    assert status == 200
    update_installations_from_config.assert_awaited_once_with(
        "config", ["policy"], ["blueprint"], force_update_data=True
    )
