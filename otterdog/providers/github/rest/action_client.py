#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from otterdog.utils import print_debug

from . import RestApi, RestClient


class ActionClient(RestClient):
    def __init__(self, rest_api: RestApi):
        super().__init__(rest_api)

    async def cancel_workflow_run(self, org_id: str, repo_name: str, run_id: str) -> bool:
        print_debug(f"cancelling workflow run #{run_id} in repo '{org_id}/{repo_name}'")

        status, body = await self.requester.request_raw(
            "POST", f"/repos/{org_id}/{repo_name}/actions/runs/{run_id}/cancel"
        )

        if status == 202:
            return True
        elif status == 409:
            return False
        else:
            raise RuntimeError(
                f"failed cancelling workflow run #{run_id} in repo '{org_id}/{repo_name}'" f"\n{status}: {body}"
            )
