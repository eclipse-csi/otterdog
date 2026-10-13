#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from unittest import mock

import pytest
from odmantic import query

from otterdog.webapp.db import service
from otterdog.webapp.db.models import PullRequestModel, TaskModel


@pytest.fixture
def odm(monkeypatch):
    odm = mock.MagicMock()
    odm.find = mock.AsyncMock(return_value=[])
    odm.count = mock.AsyncMock()

    monkeypatch.setattr(service, "mongo", mock.MagicMock(odm=odm))
    return odm


async def test_paged_total_is_the_count_without_filters(odm):
    odm.count.side_effect = [5]

    assert await service.get_tasks_paged({"pageIndex": "2", "pageSize": "10"}) == ([], 5, 5)

    odm.find.assert_awaited_once_with(TaskModel, skip=10, limit=10, sort=mock.ANY)
    odm.count.assert_awaited_once_with(TaskModel)


async def test_paged_total_ignores_the_filters_but_not_the_scope(odm):
    odm.count.side_effect = [3, 10]

    assert await service.get_open_pull_requests_paged({"id[org_id]": "eclipse-csi"}) == ([], 3, 10)

    scope = service._open_or_incomplete_pull_requests_query()
    org_filter = query.match(PullRequestModel.id.org_id, "eclipse-csi")
    odm.find.assert_awaited_once_with(PullRequestModel, scope, org_filter, skip=0, limit=20, sort=mock.ANY)
    assert odm.count.await_args_list == [
        mock.call(PullRequestModel, scope, org_filter),
        mock.call(PullRequestModel, scope),
    ]
