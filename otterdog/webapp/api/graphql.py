#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

import os
from typing import Any

from ariadne import (
    ObjectType,
    QueryType,
    load_schema_from_path,
    make_executable_schema,
    snake_case_fallback_resolvers,
)

from otterdog.utils import query_json
from otterdog.webapp.db.service import get_configurations

query = QueryType()
type_defs = load_schema_from_path(os.path.join(os.path.dirname(__file__), "schema.graphql"))

configuration_type = ObjectType("Configuration")


@query.field("projects")
async def resolve_projects(*_, filter=None):
    configurations = await get_configurations()

    if filter:
        filter = filter.replace("'", '"')
        data = [x.model_dump(exclude="id") for x in configurations]
        result = query_json(f"$[{filter}][]", data)
        configurations = result if result else []

    return configurations


@configuration_type.field("repositories")
async def resolve_repositories(config: dict[str, Any], *_, filter=None):
    repositories = config["repositories"]

    if filter:
        filter = filter.replace("'", '"')
        result = query_json(f"$[{filter}][]", repositories)
        repositories = result if result else []

    return repositories


schema = make_executable_schema(type_defs, query, configuration_type, snake_case_fallback_resolvers)
