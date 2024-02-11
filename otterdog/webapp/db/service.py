#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

from datetime import datetime
from logging import getLogger
from typing import Optional

from odmantic import query

from otterdog.webapp import mongo
from otterdog.webapp.utils import get_otterdog_config, get_rest_api_for_app

from .models import (
    ConfigurationModel,
    InstallationModel,
    InstallationStatus,
    TaskModel,
    TaskStatus,
)

logger = getLogger(__name__)


async def update_installation_status(installation_id: int, action: str) -> None:
    logger.info(f"updating installation status for installation with id '{installation_id}': {action}")

    match action:
        case "created":
            await update_installations()

        case "deleted":
            await update_installations()

        case "suspend":
            installation = await mongo.odm.find_one(
                InstallationModel, InstallationModel.installation_id == installation_id
            )

            if installation is not None:
                installation.installation_status = InstallationStatus.SUSPENDED
                await mongo.odm.save(installation)

        case "unsuspend":
            installation = await mongo.odm.find_one(
                InstallationModel, InstallationModel.installation_id == installation_id
            )

            if installation is not None:
                installation.installation_status = InstallationStatus.INSTALLED
                await mongo.odm.save(installation)

        case _:
            pass


async def update_installations() -> None:
    logger.info("updating all installations")

    rest_api = get_rest_api_for_app()
    otterdog_config = await get_otterdog_config()
    all_configured_organization_names: set[str] = set(otterdog_config.organization_names)
    all_installations = await rest_api.app.get_app_installations()

    async with mongo.odm.session() as session:
        existing_organizations: set[str] = set()
        async for org in session.find(InstallationModel):
            existing_organizations.add(org.github_id)

        for app_installation in all_installations:
            installation_id = app_installation["id"]
            github_id = app_installation["account"]["login"]
            project_name = otterdog_config.get_project_name(github_id)
            suspended_at = app_installation["suspended_at"]
            installation_status = InstallationStatus.INSTALLED if suspended_at is None else InstallationStatus.SUSPENDED

            if project_name is not None:
                org_config = otterdog_config.get_organization_config(project_name)
                config_repo = org_config.config_repo
                base_template = org_config.base_template
                all_configured_organization_names.remove(project_name)
            else:
                project_name = None
                config_repo = None
                base_template = None

            model = InstallationModel(  # type: ignore
                installation_id=installation_id,
                installation_status=installation_status,
                project_name=project_name,
                github_id=github_id,
                config_repo=config_repo,
                base_template=base_template,
            )

            if github_id in existing_organizations:
                existing_organizations.remove(github_id)

            await session.save(model)

        # process organizations that have the GitHub App not installed
        for github_id in existing_organizations:
            project_name = otterdog_config.get_project_name(github_id)
            if project_name is None:
                await session.remove(InstallationModel, InstallationModel.github_id == github_id)
            else:
                existing_model = await mongo.odm.find_one(InstallationModel, InstallationModel.github_id == github_id)

                if existing_model is not None:
                    existing_model.project_name = project_name
                    existing_model.installation_status = InstallationStatus.NOT_INSTALLED
                    await mongo.odm.save(existing_model)

        # finally add all organizations that are in the config but have the app not installed yet
        for name in all_configured_organization_names:
            config = otterdog_config.get_organization_config(name)

            if config is not None:
                model = InstallationModel(  # type: ignore
                    installation_status=InstallationStatus.NOT_INSTALLED,
                    project_name=config.name,
                    github_id=config.github_id,
                    config_repo=config.config_repo,
                    base_template=config.base_template,
                )

                await mongo.odm.save(model)


async def get_installation(installation_id: int) -> Optional[InstallationModel]:
    return await mongo.odm.find_one(InstallationModel, InstallationModel.installation_id == installation_id)


async def get_all_organization_count() -> int:
    return await mongo.odm.count(InstallationModel)


async def get_organizations() -> list[InstallationModel]:
    return await mongo.odm.find(InstallationModel)


async def get_active_organizations() -> list[InstallationModel]:
    return await mongo.odm.find(
        InstallationModel, InstallationModel.installation_status == InstallationStatus.INSTALLED
    )


async def get_tasks(limit: int) -> list[TaskModel]:
    return await mongo.odm.find(TaskModel, limit=limit, sort=query.desc(TaskModel.created_at))


async def get_configurations() -> list[ConfigurationModel]:
    return await mongo.odm.find(ConfigurationModel)


async def get_configuration_by_github_id(github_id: str) -> Optional[ConfigurationModel]:
    return await mongo.odm.find_one(ConfigurationModel, ConfigurationModel.github_id == github_id)


async def get_configuration_by_project_name(project_name: str) -> Optional[ConfigurationModel]:
    return await mongo.odm.find_one(ConfigurationModel, ConfigurationModel.project_name == project_name)


async def create_task(task: TaskModel) -> None:
    await mongo.odm.save(task)


async def finish_task(task: TaskModel) -> None:
    task.status = TaskStatus.FINISHED
    task.updated_at = datetime.utcnow()
    await mongo.odm.save(task)


async def fail_task(task: TaskModel, exception: Exception) -> None:
    task.status = TaskStatus.FAILED
    task.updated_at = datetime.utcnow()
    task.log = str(exception)
    await mongo.odm.save(task)


async def save_config(config: ConfigurationModel) -> None:
    await mongo.odm.save(config)
