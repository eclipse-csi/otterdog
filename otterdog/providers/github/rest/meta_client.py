#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************


from otterdog.logging import get_logger

from . import RestApi, RestClient

_logger = get_logger(__name__)


class MetaClient(RestClient):
    def __init__(self, rest_api: RestApi):
        super().__init__(rest_api)

    async def get_scopes(self) -> str:
        _logger.debug("retrieving token scopes")

        status, body, scopes = await self.requester.request_raw_with_scopes("GET", "/rate_limit")
        if status == 200:
            return scopes
        else:
            raise RuntimeError(f"failed retrieving token scopes:\n{body}")
