#  *******************************************************************************
#  Copyright (c) 2024-2025 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

import base64
import json
import os
import tempfile
import zipfile
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import aiofiles
import aiohttp
from pydantic import BaseModel
from quart import current_app

from otterdog.webapp import get_temporary_base_directory
from otterdog.webapp.tasks.policies import PolicyTask

if TYPE_CHECKING:
    from otterdog.providers.github.rest import RestApi
    from otterdog.webapp.policies.dependency_track_upload import DependencyTrackUploadPolicy


@dataclass(repr=False)
class UploadSBOMTask(PolicyTask):
    installation_id: int
    org_id: str
    repo_name: str
    policy: DependencyTrackUploadPolicy
    workflow_run_id: int

    @property
    def _dependency_track_token(self) -> str:
        return current_app.config["DEPENDENCY_TRACK_TOKEN"]

    async def _execute(self) -> bool:
        self.logger.info(
            "uploading sbom for repo '%s/%s'",
            self.org_id,
            self.repo_name,
        )

        async with self.get_organization_config() as _:
            rest_api = await self.rest_api

            artifacts = await rest_api.action.get_artifacts(self.org_id, self.repo_name, self.workflow_run_id)
            for artifact in artifacts:
                if artifact["name"] == self.policy.artifact_name:
                    artifact_id = artifact["id"]
                    await self._process_artifact(rest_api, artifact_id)

        return True

    async def _process_artifact(self, rest_api: RestApi, artifact_id: int) -> None:
        with tempfile.TemporaryDirectory(dir=get_temporary_base_directory()) as tmp_dir:
            artifact_file_name = os.path.join(tmp_dir, "artifact.zip")
            async with aiofiles.open(artifact_file_name, "wb") as artifact_file:
                await rest_api.action.download_artifact(artifact_file, self.org_id, self.repo_name, artifact_id)

                with zipfile.ZipFile(artifact_file_name, "r") as zip_file:
                    zip_file.extractall(tmp_dir)

                bom_file_name = os.path.join(tmp_dir, "bom.json")
                metadata_file_name = os.path.join(tmp_dir, "metadata.json")

                with open(bom_file_name) as bom_file:
                    bom = json.load(bom_file)

                with open(metadata_file_name) as metadata_file:
                    metadata = Metadata.model_validate(json.load(metadata_file))

                await self._upload_bom(bom, metadata)

    async def _upload_bom(self, bom: dict[str, Any], meta_data: Metadata) -> None:
        async with aiohttp.ClientSession() as session:
            headers = {
                "Content-Type": "application/json",
                "X-Api-Key": self._dependency_track_token,
            }

            data = {
                "projectName": meta_data.projectName,
                "projectVersion": meta_data.projectVersion,
                "parentUUID": meta_data.parentProject,
                "autoCreate": True,
                "bom": base64.b64encode(json.dumps(bom).encode("utf-8")).decode("utf-8"),
            }

            self.logger.info(
                f"uploading sbom for '{meta_data.projectName}@{meta_data.projectVersion}' to '{self.policy.base_url}'"
            )

            upload_url = f"{self.policy.base_url}/api/v1/bom"
            async with session.put(upload_url, headers=headers, json=data) as response:
                if response.status != 200:
                    error = await response.text()
                    raise RuntimeError(f"failed to upload SBOM: {error}")

    def __repr__(self) -> str:
        return f"UploadSBOMTask(repo={self.org_id}/{self.repo_name}, run_id={self.workflow_run_id})"


class Metadata(BaseModel):
    projectName: str  # noqa
    projectVersion: str  # noqa
    parentProject: str  # noqa
