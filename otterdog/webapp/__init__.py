#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from importlib import import_module
from importlib.util import find_spec

import quart_flask_patch  # type: ignore # noqa: F401
from quart import Quart
from quart_auth import QuartAuth

from .config import AppConfig
from .db import Mongo, init_mongo_database

_BLUEPRINT_MODULES: list[str] = ["home"]

mongo = Mongo()
auth_manager = QuartAuth()


def register_extensions(app):
    mongo.init_app(app)
    auth_manager.init_app(app)


def register_github_webhook(app) -> None:
    webhook_fqn = "otterdog.webapp.webhook"
    spec = find_spec(webhook_fqn)
    if spec is not None:
        module = import_module(webhook_fqn)
        module.webhook.init_app(app)


def register_blueprints(app):
    for module_name in _BLUEPRINT_MODULES:
        routes_fqn = f"otterdog.webapp.{module_name}.routes"
        spec = find_spec(routes_fqn)
        if spec is not None:
            module = import_module(routes_fqn)
            app.register_blueprint(module.blueprint)


def configure_database(app):
    @app.before_serving
    async def configure():
        async with app.app_context():
            await init_mongo_database(mongo)


def create_app(app_config: AppConfig):
    app = Quart(app_config.QUART_APP)
    app.config.from_object(app_config)

    register_extensions(app)
    register_github_webhook(app)
    register_blueprints(app)
    configure_database(app)

    @app.template_filter("status")
    def status_color(status):
        from otterdog.webapp.db.models import InstallationStatus

        match status:
            case InstallationStatus.installed:
                return "success"
            case InstallationStatus.not_installed:
                return "danger"
            case InstallationStatus.suspended:
                return "warning"
            case _:
                return "info"

    return app
