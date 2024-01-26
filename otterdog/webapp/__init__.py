#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from importlib import import_module
from importlib.util import find_spec

from quart import Quart

from .config import AppConfig

_BLUEPRINT_MODULES: list[str] = []


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


def create_app(app_config: AppConfig):
    app = Quart(app_config.QUART_APP)
    app.config.from_object(app_config)

    register_github_webhook(app)
    register_blueprints(app)

    return app
