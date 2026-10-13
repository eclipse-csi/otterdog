#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from unittest import mock

from otterdog.webapp.api import routes


async def test_paged_endpoints_return_the_filtered_and_total_counts(app, monkeypatch):
    """
    Exercised through a request context rather than a test client.

    Booting the app would run its startup hooks, which expect a running mongodb.
    """

    get_tasks_paged = mock.AsyncMock(return_value=([], 3, 10))
    monkeypatch.setattr(routes, "get_tasks_paged", get_tasks_paged)

    async with app.test_request_context("/api/tasks?pageIndex=1&org_id=eclipse-csi"):
        response = await routes.tasks()

    assert await response.get_json() == {"data": [], "itemsCount": 3, "totalCount": 10}
    get_tasks_paged.assert_awaited_once_with({"pageIndex": "1", "org_id": "eclipse-csi"})
