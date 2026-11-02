#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import json
from unittest.mock import AsyncMock

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
