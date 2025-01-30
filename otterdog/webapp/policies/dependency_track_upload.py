#  *******************************************************************************
#  Copyright (c) 2024-2025 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import re
from logging import getLogger
from typing import Any, Self

from quart import current_app

from otterdog.utils import expect_type, unwrap
from otterdog.webapp.webhook.github_models import WorkflowRun

from . import Policy, PolicyType

logger = getLogger(__name__)


class DependencyTrackUploadPolicy(Policy):
    """
    A policy to upload sbom data from workflow runs to dependency track.
    """

    artifact_name: str
    workflow_filter: str

    @property
    def type(self) -> PolicyType:
        return PolicyType.DEPENDENCY_TRACK_UPLOAD

    def matches_workflow(self, workflow: str) -> bool:
        return re.search(self.workflow_filter, workflow) is not None

    def merge(self, other: Self) -> Self:
        copy = super().merge(other)
        copy.workflow_filter = other.workflow_filter
        return copy

    async def evaluate(
        self,
        installation_id: int,
        github_id: str,
        repo_name: str | None = None,
        payload: Any | None = None,
    ) -> None:
        repo_name = unwrap(repo_name)
        payload = expect_type(payload, WorkflowRun)

        if (
            payload.conclusion == "success"
            and payload.referenced_workflows is not None
            and any(self.matches_workflow(x.path) for x in payload.referenced_workflows)
        ):
            from otterdog.webapp.tasks.policies.upload_sbom import UploadSBOMTask

            logger.info(
                f"workflow run {payload.name}/#{payload.id} in repo '{github_id}/{repo_name}' contains sbom data"
            )

            current_app.add_background_task(
                UploadSBOMTask(
                    installation_id,
                    github_id,
                    repo_name,
                    self,
                    payload.id,
                )
            )
