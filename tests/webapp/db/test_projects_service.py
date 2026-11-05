#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

"""The data of the organizations read by the projects pages, by their GitHub id."""

from datetime import datetime
from unittest import mock

import pytest
from bson import ObjectId

from otterdog.webapp.db import service
from otterdog.webapp.db.models import StatisticsModel, TaskModel, TaskStatus


class _AggregatingCollection:
    """A collection returning the given documents for any aggregation, keeping the pipeline it was given."""

    def __init__(self, documents):
        self.documents = documents
        self.pipeline = None

    def aggregate(self, pipeline):
        self.pipeline = pipeline
        cursor = mock.Mock()
        cursor.to_list = mock.AsyncMock(return_value=self.documents)
        return cursor


@pytest.fixture
def database(monkeypatch):
    engine = mock.Mock()
    monkeypatch.setattr(type(service.mongo), "odm", mock.PropertyMock(return_value=engine))
    return engine


async def test_the_statistics_by_organization(database):
    statistics = StatisticsModel(
        project_name="ecd.che",
        github_id="eclipse-che",
        two_factor_enforced=1,
        total_repos=3,
        archived_repos=0,
        repos_with_secret_scanning=0,
        repos_with_secret_scanning_push_protection=0,
        repos_with_branch_protection=0,
        repos_with_dependabot_alerts=0,
        repos_with_dependabot_security_updates=0,
        repos_with_private_vulnerability_reporting=0,
    )
    database.find = mock.AsyncMock(return_value=[statistics])

    assert await service.get_statistics_by_github_id() == {"eclipse-che": statistics}


async def test_the_latest_task_of_each_organization(database):
    collection = _AggregatingCollection(
        [
            {
                "_id": "eclipse-che",
                "task": {
                    "_id": ObjectId(),
                    "type": "FetchConfigTask",
                    "org_id": "eclipse-che",
                    "repo_name": ".eclipsefdn",
                    "status": "failed",
                    "log": "failed to evaluate",
                    "created_at": datetime(2026, 11, 5, 9, 0),
                    "updated_at": datetime(2026, 11, 5, 9, 1),
                },
            }
        ]
    )
    database.get_collection.return_value = collection

    tasks = await service.get_latest_tasks_by_organization("FetchConfigTask")

    # the tasks of the type that ran to their end, not the ones scheduled again, the latest first, the first one of
    # each organization
    assert collection.pipeline[0] == {"$match": {"type": "FetchConfigTask", "status": {"$in": ["finished", "failed"]}}}
    assert collection.pipeline[1] == {"$sort": {"created_at": -1}}
    assert isinstance(tasks["eclipse-che"], TaskModel)
    assert (tasks["eclipse-che"].status, tasks["eclipse-che"].log) == (TaskStatus.FAILED, "failed to evaluate")


async def test_the_latest_task_of_an_organization(database):
    collection = _AggregatingCollection([])
    database.get_collection.return_value = collection

    assert await service.get_latest_tasks_by_organization("FetchConfigTask", "eclipse-che") == {}
    assert collection.pipeline[0] == {
        "$match": {"type": "FetchConfigTask", "status": {"$in": ["finished", "failed"]}, "org_id": "eclipse-che"}
    }


async def test_the_open_pull_requests_of_each_organization(database):
    collection = _AggregatingCollection([{"_id": "eclipse-che", "count": 2}])
    database.get_collection.return_value = collection

    assert await service.get_open_pull_request_counts_by_organization() == {"eclipse-che": 2}
    # counted by mongodb, only the open ones
    assert collection.pipeline == [
        {"$match": {"status": "open"}},
        {"$group": {"_id": "$_id.org_id", "count": {"$sum": 1}}},
    ]


async def test_the_open_pull_requests_of_an_organization(database):
    collection = _AggregatingCollection([])
    database.get_collection.return_value = collection

    assert await service.get_open_pull_request_counts_by_organization("eclipse-che") == {}
    assert collection.pipeline[0] == {"$match": {"status": "open", "_id.org_id": "eclipse-che"}}


async def test_the_blueprint_statuses_of_each_organization(database):
    database.get_collection.return_value = _AggregatingCollection(
        [
            {"_id": {"org_id": "eclipse-che", "status": "failure"}, "count": 2},
            {"_id": {"org_id": "eclipse-che", "status": "success"}, "count": 5},
            {"_id": {"org_id": "eclipse-csi", "status": "success"}, "count": 1},
        ]
    )

    assert await service.get_blueprint_status_counts_by_organization() == {
        "eclipse-che": {"failure": 2, "success": 5},
        "eclipse-csi": {"success": 1},
    }


async def test_the_scorecard_average_of_each_organization(database):
    collection = _AggregatingCollection([{"_id": "eclipse-che", "score": 6.5}])
    database.get_collection.return_value = collection

    assert await service.get_scorecard_averages_by_organization() == {"eclipse-che": 6.5}
    # the repositories without a score do not count
    assert collection.pipeline[0] == {"$match": {"score": {"$ne": None}}}
