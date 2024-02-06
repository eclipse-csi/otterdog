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
from flask_sqlalchemy import SQLAlchemy
from quart import Quart
from quart_auth import QuartAuth

from .config import AppConfig
from .db import Base

_BLUEPRINT_MODULES: list[str] = ["home"]

db = SQLAlchemy(model_class=Base)
auth_manager = QuartAuth()


def register_extensions(app):
    db.init_app(app)
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
    async def create_tables():
        async with app.app_context():
            models_fqn = "otterdog.webapp.db.models"
            import_module(models_fqn)
            db.create_all()

    @app.before_serving
    async def fill_database():
        from otterdog.webapp.db.service import fill_organization_table

        await fill_organization_table(app)

    @app.teardown_request
    def shutdown_session(exception=None):
        db.session.remove()


def create_app(app_config: AppConfig):
    app = Quart(app_config.QUART_APP)
    app.config.from_object(app_config)

    register_extensions(app)
    register_github_webhook(app)
    register_blueprints(app)
    configure_database(app)

    return app
