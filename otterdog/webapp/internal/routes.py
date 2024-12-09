#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from otterdog.webapp.blueprints import create_blueprint_from_model
from otterdog.webapp.db.service import (
    get_active_installations,
    get_blueprints_by_last_checked_time,
    get_installation_by_github_id,
    logger,
    save_blueprint,
    update_data_for_installation,
    update_installations_from_config,
)
from otterdog.webapp.utils import (
    current_utc_time,
    has_minimum_timedelta_elapsed,
    refresh_global_blueprints,
    refresh_global_policies,
    refresh_otterdog_config,
)

from . import blueprint


@blueprint.route("/health")
async def health():
    return {}, 200


@blueprint.route("/init")
async def init():
    config = await refresh_otterdog_config()
    policies = await refresh_global_policies()
    blueprints = await refresh_global_blueprints()
    await update_installations_from_config(config, policies, blueprints)

    for installation in await get_active_installations():
        await update_data_for_installation(installation)

    return {}, 200


@blueprint.route("/check", defaults={"limit": 50})
@blueprint.route("/check/<int:limit>")
async def check(limit: int):
    from datetime import timedelta

    logger.info("checking blueprints...")

    for blueprint_model in await get_blueprints_by_last_checked_time(limit=limit):
        org_id = blueprint_model.id.org_id

        if blueprint_model.last_checked is not None and not has_minimum_timedelta_elapsed(
            blueprint_model.last_checked, timedelta(hours=1)
        ):
            logger.debug(
                "skipping blueprint with id '%s' for org '%s', last checked at '%s'",
                blueprint_model.id.blueprint_id,
                org_id,
                blueprint_model.last_checked.strftime("%d/%m/%Y %H:%M:%S"),
            )
            continue

        installation = await get_installation_by_github_id(org_id)
        if installation is None:
            logger.error("no installation model found for org '%s'", org_id)
            continue

        logger.debug("checking blueprint with id '%s' for org '%s'...", blueprint_model.id.blueprint_id, org_id)

        blueprint_instance = create_blueprint_from_model(blueprint_model)
        await blueprint_instance.evaluate(installation.installation_id, org_id, blueprint_model.recheck_needed)

        blueprint_model.last_checked = current_utc_time()

        # if we were forced to do a recheck, reset it afterward
        if blueprint_model.recheck_needed is True:
            blueprint_model.recheck_needed = False

        await save_blueprint(blueprint_model)

    return {}, 200


@blueprint.route("/<template>")
async def route_template(template: str):
    return {}, 404


@blueprint.errorhandler(Exception)
async def error_exception(error):
    import traceback

    traceback.print_exception(error)
    return {}, 500
