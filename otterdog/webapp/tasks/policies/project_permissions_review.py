#  *******************************************************************************
#  Copyright (c) 2024-2025 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from otterdog.webapp.tasks.policies import PolicyTask

if TYPE_CHECKING:
    from otterdog.providers.github.rest import RestApi
    from otterdog.webapp.policies.project_permissions_review import ProjectPermissionsReviewPolicy


@dataclass(repr=False)
class ProjectPermissionsReviewTask(PolicyTask):
    installation_id: int
    org_id: str
    repo_name: str
    policy: ProjectPermissionsReviewPolicy
    workflow_run_id: int

    async def _execute(self) -> bool:
        self.logger.info(
            "creating project permissions review issue for repo '%s/%s'",
            self.org_id,
            self.repo_name,
        )

        async with self.get_organization_config() as _:
            rest_api = await self.rest_api
            await self._create_review_issue(rest_api)

        return True

    async def _create_review_issue(self, rest_api: RestApi) -> None:
        """Create a new project permissions review issue."""
        # Try to fetch custom content from artifact or repository file
        custom_title, custom_body = await self._fetch_custom_content(rest_api)

        issue_title = custom_title if custom_title else self.policy.issue_title
        issue_body = self.policy.get_issue_body(self.repo_name, self.org_id, custom_body)

        self.logger.info(
            "creating project permissions review issue for repo '%s/%s'",
            self.org_id,
            self.repo_name,
        )

        await rest_api.issue.create_issue(
            self.org_id,
            self.repo_name,
            issue_title,
            issue_body,
        )

    async def _fetch_custom_content(self, rest_api: RestApi) -> tuple[str | None, str | None]:
        """Fetch custom title and body from artifact or repository file."""
        import json
        import os
        import tempfile
        import zipfile

        import aiofiles

        from otterdog.webapp import get_temporary_base_directory

        # First, try to fetch from artifact if configured
        if self.policy.artifact_name:
            try:
                artifacts = await rest_api.action.get_artifacts(self.org_id, self.repo_name, self.workflow_run_id)

                for artifact in artifacts:
                    if artifact["name"] == self.policy.artifact_name:
                        artifact_id = artifact["id"]

                        with tempfile.TemporaryDirectory(dir=get_temporary_base_directory()) as tmp_dir:
                            artifact_file_name = os.path.join(tmp_dir, "artifact.zip")
                            async with aiofiles.open(artifact_file_name, "wb") as artifact_file:
                                await rest_api.action.download_artifact(
                                    artifact_file, self.org_id, self.repo_name, artifact_id
                                )

                            with zipfile.ZipFile(artifact_file_name, "r") as zip_file:
                                zip_file.extractall(tmp_dir)

                            content_file = os.path.join(tmp_dir, "content.json")
                            if os.path.exists(content_file):
                                with open(content_file) as f:
                                    content = json.load(f)
                                    return content.get("title"), content.get("body")

            except Exception as e:
                self.logger.debug(f"Could not fetch custom content from artifact: {e}")

        # Fallback to repository file
        try:
            content = await rest_api.content.get_content(
                self.org_id,
                self.repo_name,
                ".github/project-permissions-review-body.md",
            )
            if content and isinstance(content, str):
                return None, content
        except Exception as e:
            self.logger.debug(f"No custom issue body found at .github/project-permissions-review-body.md: {e}")

        return None, None

    def __repr__(self) -> str:
        return f"ProjectPermissionsReviewTask(repo={self.org_id}/{self.repo_name})"
