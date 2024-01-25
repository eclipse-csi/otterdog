#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import base64
from typing import Any, Optional

from otterdog.providers.github.exception import GitHubException
from otterdog.utils import print_debug

from . import RestApi, RestClient


class ContentClient(RestClient):
    def __init__(self, rest_api: RestApi):
        super().__init__(rest_api)

    async def get_content_object(
        self, org_id: str, repo_name: str, path: str, ref: Optional[str] = None
    ) -> dict[str, Any]:
        print_debug(f"retrieving content '{path}' from repo '{org_id}/{repo_name}'")

        try:
            if ref is not None:
                params = {"ref": ref}
            else:
                params = None

            return await self.requester.async_request_json(
                "GET", f"/repos/{org_id}/{repo_name}/contents/{path}", params=params
            )
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed retrieving content '{path}' from repo '{repo_name}':\n{ex}").with_traceback(tb)

    async def get_content(self, org_id: str, repo_name: str, path: str, ref: Optional[str]) -> str:
        json_response = await self.get_content_object(org_id, repo_name, path, ref)
        return base64.b64decode(json_response["content"]).decode("utf-8")

    async def update_content(
        self,
        org_id: str,
        repo_name: str,
        path: str,
        content: str,
        message: Optional[str] = None,
    ) -> bool:
        print_debug(f"putting content '{path}' to repo '{org_id}/{repo_name}'")

        try:
            json_response = await self.get_content_object(org_id, repo_name, path)
            old_sha = json_response["sha"]
            old_content = base64.b64decode(json_response["content"]).decode("utf-8")
        except RuntimeError:
            old_sha = None
            old_content = None

        # check if the content has changed, otherwise do not update
        if old_content is not None and content == old_content:
            print_debug("not updating content, no changes")
            return False

        base64_encoded_data = base64.b64encode(content.encode("utf-8"))
        base64_content = base64_encoded_data.decode("utf-8")

        if message is None:
            push_message = f"Updating file '{path}' with otterdog."
        else:
            push_message = message

        data = {
            "message": push_message,
            "content": base64_content,
        }

        if old_sha is not None:
            data["sha"] = old_sha

        try:
            await self.requester.async_request_json("PUT", f"/repos/{org_id}/{repo_name}/contents/{path}", data)
            return True
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed putting content '{path}' to repo '{repo_name}':\n{ex}").with_traceback(tb)

    async def delete_content(
        self,
        org_id: str,
        repo_name: str,
        path: str,
        message: Optional[str] = None,
    ) -> bool:
        print_debug(f"deleting content '{path}' in repo '{org_id}/{repo_name}'")

        try:
            json_response = await self.get_content_object(org_id, repo_name, path)
            old_sha = json_response["sha"]
        except RuntimeError:
            old_sha = None

        if old_sha is None:
            return False

        if message is None:
            push_message = f"Deleting file '{path}' with otterdog."
        else:
            push_message = message

        data = {"message": push_message, "sha": old_sha}

        try:
            await self.requester.async_request_json("DELETE", f"/repos/{org_id}/{repo_name}/contents/{path}", data)
            return True
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed deleting content '{path}' in repo '{repo_name}':\n{ex}").with_traceback(tb)
