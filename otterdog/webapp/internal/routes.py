#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from quart import (
    render_template,
)

from otterdog.webapp.blueprints import create_blueprint_from_model
from otterdog.webapp.db.service import (
    get_active_installations,
    get_blueprints,
    logger,
    update_data_for_installation,
    update_installations_from_config,
)
from otterdog.webapp.utils import refresh_global_blueprints, refresh_global_policies, refresh_otterdog_config

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


@blueprint.route("/check")
async def check():
    logger.debug("checking blueprints...")

    for installation in await get_active_installations():
        org_id = installation.github_id
        logger.debug(f"checking org '{org_id}'")

        for blueprint_model in await get_blueprints(org_id):
            blueprint_instance = create_blueprint_from_model(blueprint_model)
            await blueprint_instance.evaluate(installation.installation_id, org_id)

    return {}, 200


@blueprint.route("/<template>")
async def route_template(template: str):
    return await render_template("home/page-404.html"), 404


@blueprint.errorhandler(Exception)
async def error_exception(error):
    import traceback

    traceback.print_exception(error)
    return await render_template("home/page-500.html"), 500
