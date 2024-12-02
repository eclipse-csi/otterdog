#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import base64
from typing import Any

from otterdog.logging import get_logger
from otterdog.providers.github.exception import GitHubException

from . import RestApi, RestClient

_logger = get_logger(__name__)


class ContentClient(RestClient):
    def __init__(self, rest_api: RestApi):
        super().__init__(rest_api)

    async def get_contents(
        self, org_id: str, repo_name: str, path: str, ref: str | None = None
    ) -> list[dict[str, Any]]:
        json_response = await self.get_content_object(org_id, repo_name, path, ref)
        if not isinstance(json_response, list):
            raise RuntimeError(f"unexpected result for retrieving contents of path '{path}': '{type(json_response)}'")
        return json_response

    async def get_content_object(
        self, org_id: str, repo_name: str, path: str, ref: str | None = None
    ) -> dict[str, Any] | list[dict]:
        _logger.debug("retrieving content '%s' from repo '%s/%s'", path, org_id, repo_name)

        try:
            params = {"ref": ref} if ref is not None else None

            return await self.requester.request_json(
                "GET", f"/repos/{org_id}/{repo_name}/contents/{path}", params=params
            )
        except GitHubException as ex:
            raise RuntimeError(f"failed retrieving content '{path}' from repo '{repo_name}':\n{ex}") from ex

    async def get_content(self, org_id: str, repo_name: str, path: str, ref: str | None = None) -> str:
        json_response = await self.get_content_object(org_id, repo_name, path, ref)
        if not isinstance(json_response, dict):
            raise RuntimeError(f"unexpected result for retrieving content of path '{path}': '{type(json_response)}'")
        return base64.b64decode(json_response["content"]).decode("utf-8")

    async def get_content_with_sha(
        self, org_id: str, repo_name: str, path: str, ref: str | None = None
    ) -> tuple[str, str]:
        json_response = await self.get_content_object(org_id, repo_name, path, ref)
        if not isinstance(json_response, dict):
            raise RuntimeError(f"unexpected result for retrieving content of path '{path}': '{type(json_response)}'")
        return base64.b64decode(json_response["content"]).decode("utf-8"), json_response["sha"]

    async def update_content(
        self,
        org_id: str,
        repo_name: str,
        path: str,
        content: str,
        ref: str | None = None,
        message: str | None = None,
        author_name: str | None = None,
        author_email: str | None = None,
        author_is_committer: bool = False,
    ) -> bool:
        _logger.debug("putting content '%s' to repo '%s/%s'", path, org_id, repo_name)

        try:
            json_response = await self.get_content_object(org_id, repo_name, path, ref)
            if not isinstance(json_response, dict):
                raise RuntimeError(
                    f"unexpected result for retrieving content of path '{path}': '{type(json_response)}'"
                )
            old_sha = json_response["sha"]
            old_content = base64.b64decode(json_response["content"]).decode("utf-8")
        except RuntimeError:
            old_sha = None
            old_content = None

        # check if the content has changed, otherwise do not update
        if old_content is not None and content == old_content:
            _logger.debug("not updating content, no changes")
            return False

        base64_encoded_data = base64.b64encode(content.encode("utf-8"))
        base64_content = base64_encoded_data.decode("utf-8")

        push_message = f"Updating file '{path}' with otterdog." if message is None else message

        data: dict[str, Any] = {
            "message": push_message,
            "content": base64_content,
        }

        if ref is not None:
            data["branch"] = ref

        if author_name is not None:
            author = {
                "name": author_name,
                "email": author_email if author_email is not None else "",
            }
            data["author"] = author

            if author_is_committer is True:
                data["committer"] = author

        if old_sha is not None:
            data["sha"] = old_sha

        try:
            await self.requester.request_json("PUT", f"/repos/{org_id}/{repo_name}/contents/{path}", data)
            return True
        except GitHubException as ex:
            raise RuntimeError(f"failed putting content '{path}' to repo '{repo_name}':\n{ex}") from ex

    async def delete_content(
        self,
        org_id: str,
        repo_name: str,
        path: str,
        message: str | None = None,
    ) -> bool:
        _logger.debug("deleting content '%s' in repo '%s/%s'", path, org_id, repo_name)

        try:
            json_response = await self.get_content_object(org_id, repo_name, path)
            if not isinstance(json_response, dict):
                raise RuntimeError(
                    f"unexpected result for retrieving content of path '{path}': '{type(json_response)}'"
                )
            old_sha = json_response["sha"]
        except RuntimeError:
            old_sha = None

        if old_sha is None:
            return False

        push_message = f"Deleting file '{path}' with otterdog." if message is None else message

        data = {"message": push_message, "sha": old_sha}

        try:
            await self.requester.request_json("DELETE", f"/repos/{org_id}/{repo_name}/contents/{path}", data)
            return True
        except GitHubException as ex:
            raise RuntimeError(f"failed deleting content '{path}' in repo '{repo_name}':\n{ex}") from ex
