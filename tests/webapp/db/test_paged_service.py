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
from otterdog.webapp.db.models import BlueprintStatus, BlueprintStatusModel, PullRequestModel, TaskModel


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


async def test_paged_merged_pull_requests_have_their_own_scope_and_order(odm):
    odm.count.side_effect = [0]

    await service.get_merged_pull_requests_paged({})

    odm.find.assert_awaited_once_with(
        PullRequestModel,
        service._merged_pull_requests_query(),
        skip=0,
        limit=20,
        sort=query.desc(PullRequestModel.merged_at),
    )


async def test_paged_pull_requests_filter_booleans_and_sort_by_id(odm):
    odm.count.side_effect = [1, 2]

    await service.get_open_pull_requests_paged(
        {"draft": "true", "id[pull_request]": "25", "sortField": "id.pull_request", "sortOrder": "asc"}
    )

    odm.find.assert_awaited_once_with(
        PullRequestModel,
        service._open_or_incomplete_pull_requests_query(),
        query.eq(PullRequestModel.draft, True),
        query.match(PullRequestModel.id.pull_request, 25),
        skip=0,
        limit=20,
        sort=query.asc(PullRequestModel.id.pull_request),
    )


async def test_paged_pull_requests_reject_unknown_id_fields(odm):
    with pytest.raises(RuntimeError, match="unexpected id field 'unknown'"):
        await service.get_open_pull_requests_paged({"id[unknown]": "x"})


@pytest.mark.parametrize(
    ("get_blueprints_paged", "status"),
    [
        (service.get_blueprints_with_remediations_paged, BlueprintStatus.REMEDIATION_PREPARED),
        (service.get_dismissed_blueprints_paged, BlueprintStatus.DISMISSED),
    ],
)
async def test_paged_blueprints_are_scoped_by_status(odm, get_blueprints_paged, status):
    odm.count.side_effect = [0]

    await get_blueprints_paged({})

    odm.find.assert_awaited_once_with(
        BlueprintStatusModel,
        query.match(BlueprintStatusModel.status, status),
        skip=0,
        limit=20,
        sort=query.desc(BlueprintStatusModel.updated_at),
    )
