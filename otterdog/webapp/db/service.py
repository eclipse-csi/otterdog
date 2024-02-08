#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

from logging import getLogger
from typing import Optional

from odmantic import query

from otterdog.webapp import mongo
from otterdog.webapp.utils import get_otterdog_config, get_rest_api_for_app

from .models import InstallationStatus, OrganizationConfigModel, TaskModel

logger = getLogger(__name__)


async def get_organization_config_by_installation_id(installation_id: int) -> Optional[OrganizationConfigModel]:
    config = await mongo.odm.find_one(
        OrganizationConfigModel, OrganizationConfigModel.installation_id == installation_id
    )

    if config is None:
        logger.error(f"did not find an OrganizationConfig document for installation_id '{installation_id}'")

    return config


async def update_installation_status(installation_id: int, action: str) -> None:
    logger.info(f"updating installation status for installation with id '{installation_id}': {action}")

    match action:
        case "created":
            await update_organization_configs()

        case "deleted":
            await update_organization_configs()

        case "suspend":
            installation = await mongo.odm.find_one(
                OrganizationConfigModel, OrganizationConfigModel.installation_id == installation_id
            )

            if installation is not None:
                installation.installation_status = InstallationStatus.suspended
                await mongo.odm.save(installation)

        case "unsuspend":
            installation = await mongo.odm.find_one(
                OrganizationConfigModel, OrganizationConfigModel.installation_id == installation_id
            )

            if installation is not None:
                installation.installation_status = InstallationStatus.installed
                await mongo.odm.save(installation)

        case _:
            pass


async def update_organization_configs() -> None:
    logger.info("updating all organization configs")

    rest_api = get_rest_api_for_app()
    otterdog_config = await get_otterdog_config()
    all_configured_organization_names: set[str] = set(otterdog_config.organization_names)
    all_installations = await rest_api.app.get_app_installations()

    async with mongo.odm.session() as session:
        existing_organizations: set[str] = set()
        async for org in session.find(OrganizationConfigModel):
            existing_organizations.add(org.github_id)

        for app_installation in all_installations:
            installation_id = app_installation["id"]
            github_id = app_installation["account"]["login"]
            project_name = otterdog_config.get_project_name(github_id)
            suspended_at = app_installation["suspended_at"]
            installation_status = InstallationStatus.installed if suspended_at is None else InstallationStatus.suspended

            if project_name is not None:
                org_config = otterdog_config.get_organization_config(project_name)
                config_repo = org_config.config_repo
                base_template = org_config.base_template
                all_configured_organization_names.remove(project_name)
            else:
                project_name = None
                config_repo = None
                base_template = None

            model = OrganizationConfigModel(  # type: ignore
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
                await session.remove(OrganizationConfigModel, OrganizationConfigModel.github_id == github_id)
            else:
                existing_model = await mongo.odm.find_one(
                    OrganizationConfigModel, OrganizationConfigModel.github_id == github_id
                )

                if existing_model is not None:
                    existing_model.project_name = project_name
                    existing_model.installation_status = InstallationStatus.not_installed
                    await mongo.odm.save(existing_model)

        # finally add all organizations that are in the config but have the app not installed yet
        for name in all_configured_organization_names:
            config = otterdog_config.get_organization_config(name)

            if config is not None:
                model = OrganizationConfigModel(  # type: ignore
                    installation_status=InstallationStatus.not_installed,
                    project_name=config.name,
                    github_id=config.github_id,
                    config_repo=config.config_repo,
                    base_template=config.base_template,
                )

                await mongo.odm.save(model)


async def get_organization_count() -> int:
    return await mongo.odm.count(OrganizationConfigModel)


async def get_organizations() -> list[OrganizationConfigModel]:
    return await mongo.odm.find(OrganizationConfigModel)


async def get_tasks(limit: int) -> list[TaskModel]:
    return await mongo.odm.find(TaskModel, limit=limit, sort=query.desc(TaskModel.created_at))
