#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import json
from unittest.mock import AsyncMock

import pytest

from otterdog.providers.github.auth import token_auth
from otterdog.providers.github.graphql import GraphQLClient


async def test_team_membership_ignores_unresolved_teams():
    client = GraphQLClient(token_auth("token"))

    # a partial response returns a team that failed to resolve as a null node
    response = {
        "data": {
            "organization": {
                "teams": {
                    "nodes": [{"id": "T_1", "name": "project-leads", "slug": "project-leads"}, None],
                    "pageInfo": {"endCursor": None, "hasNextPage": False},
                }
            }
        },
        "errors": [{"message": "Something went wrong while executing your query."}],
    }
    client._request_raw = AsyncMock(return_value=(200, json.dumps(response)))

    try:
        teams = await client.get_team_membership("org", "lead")
    finally:
        await client.close()

    assert teams == [{"id": "T_1", "name": "project-leads", "slug": "project-leads"}]


async def _query(client: GraphQLClient, response: dict, method: str, *args):
    client._request_raw = AsyncMock(return_value=(200, json.dumps(response)))
    try:
        return await getattr(client, method)(*args)
    finally:
        await client.close()


async def test_issue_comment_is_returned():
    comment = {"id": "IC_1", "body": "body", "isMinimized": False}

    result = await _query(GraphQLClient(token_auth("token")), {"data": {"node": comment}}, "get_issue_comment", "IC_1")

    assert result == comment


async def test_deleted_issue_comment_is_none():
    response = {"data": {"node": None}, "errors": [{"type": "NOT_FOUND", "message": "Could not resolve to a node"}]}

    assert await _query(GraphQLClient(token_auth("token")), response, "get_issue_comment", "IC_1") is None


async def test_failed_retrieval_of_an_issue_comment_raises():
    # not taken for a deleted comment, which would not be updated anymore
    response = {"data": {"node": None}, "errors": [{"message": "Something went wrong while executing your query."}]}

    with pytest.raises(RuntimeError, match="failed retrieving comment"):
        await _query(GraphQLClient(token_auth("token")), response, "get_issue_comment", "IC_1")


async def test_failed_update_of_an_issue_comment_raises():
    # GitHub answers a failed mutation with a 200
    response = {"data": {"updateIssueComment": None}, "errors": [{"type": "FORBIDDEN", "message": "forbidden"}]}

    with pytest.raises(RuntimeError, match="failed updating comment"):
        await _query(GraphQLClient(token_auth("token")), response, "update_issue_comment", "IC_1", "body")
