#  *******************************************************************************
#  Copyright (c) 2023-2025 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import os
import secrets

from decouple import config  # type: ignore

# Settings that must never resolve to an empty value: they are either used
# to build outgoing requests/identifiers (URLs, hostnames, commit status
# contexts) or are otherwise required for the application to function.
REQUIRED_NON_EMPTY_SETTINGS = (
    "BASE_URL",
    "ASSETS_ROOT",
    "APP_ROOT",
    "MONGO_URI",
    "REDIS_URI",
    "GHPROXY_URI",
    "GITHUB_ADMIN_TEAMS",
    "GITHUB_WEBHOOK_ENDPOINT",
    "GITHUB_WEBHOOK_VALIDATION_CONTEXT",
    "GITHUB_WEBHOOK_SYNC_CONTEXT",
    "GITHUB_APP_ID",
    "GITHUB_APP_PRIVATE_KEY",
    "PROJECTS_BASE_URL",
    "DEPENDENCY_TRACK_URL",
    "DEPENDENCY_TRACK_TOKEN",
    "OTTERDOG_CONFIG_OWNER",
    "OTTERDOG_CONFIG_REPO",
    "OTTERDOG_CONFIG_PATH",
    "OTTERDOG_CONFIG_TOKEN",
)


def validate_required_settings(config_cls: type) -> None:
    """Raise a ValueError if any setting in REQUIRED_NON_EMPTY_SETTINGS is empty on config_cls."""
    for name in REQUIRED_NON_EMPTY_SETTINGS:
        if not getattr(config_cls, name, None):
            raise ValueError(f"{name} must not be empty")


class AppConfig:
    QUART_APP = "otterdog.webapp"

    BASE_URL = config("BASE_URL")

    # Assets Management
    ASSETS_ROOT = config("ASSETS_ROOT", default="/static/assets")

    CACHE_CONTROL = config("CACHE_CONTROL", default=False)

    APP_ROOT = config("APP_ROOT")
    DB_ROOT = os.path.join(APP_ROOT, "db")

    MONGO_URI = config("MONGO_URI", default="mongodb://mongodb:27017/otterdog")
    REDIS_URI = config("REDIS_URI", default="redis://redis:6379")
    GHPROXY_URI = config("GHPROXY_URI", default="http://ghproxy:8888")

    OTTERDOG_CONFIG_OWNER = config("OTTERDOG_CONFIG_OWNER", default=None)
    OTTERDOG_CONFIG_REPO = config("OTTERDOG_CONFIG_REPO", default=None)
    OTTERDOG_CONFIG_PATH = config("OTTERDOG_CONFIG_PATH", default=None)
    OTTERDOG_CONFIG_TOKEN = config("OTTERDOG_CONFIG_TOKEN", default=None)

    # Set up the App SECRET_KEY
    SECRET_KEY = config("SECRET_KEY", default=None)
    if not SECRET_KEY:
        SECRET_KEY = secrets.token_hex(16)

    GITHUB_ADMIN_TEAMS = config("GITHUB_ADMIN_TEAMS", default="otterdog-admins")
    GITHUB_WEBHOOK_ENDPOINT = config("GITHUB_WEBHOOK_ENDPOINT", default="/github-webhook/receive")
    GITHUB_WEBHOOK_SECRET = config("GITHUB_WEBHOOK_SECRET", default=None)
    GITHUB_WEBHOOK_VALIDATION_CONTEXT = config("GITHUB_WEBHOOK_VALIDATION_CONTEXT", default="otterdog-validate")
    GITHUB_WEBHOOK_SYNC_CONTEXT = config("GITHUB_WEBHOOK_SYNC_CONTEXT", default="otterdog-sync")

    # GitHub OAuth config
    GITHUB_CLIENT_ID = config("GITHUB_OAUTH_CLIENT_ID", default=None)
    GITHUB_CLIENT_SECRET = config("GITHUB_OAUTH_CLIENT_SECRET", default=None)

    # GitHub App config
    GITHUB_APP_ID = config("GITHUB_APP_ID")
    GITHUB_APP_PRIVATE_KEY = config("GITHUB_APP_PRIVATE_KEY")

    PROJECTS_BASE_URL = config("PROJECTS_BASE_URL", default="https://projects.eclipse.org/projects/")
    DEPENDENCY_TRACK_URL = config("DEPENDENCY_TRACK_URL")
    DEPENDENCY_TRACK_TOKEN = config("DEPENDENCY_TRACK_TOKEN")


validate_required_settings(AppConfig)


class ProductionConfig(AppConfig):
    DEBUG = False

    # Security
    SESSION_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_DURATION = 3600


class DebugConfig(AppConfig):
    DEBUG = True

    TEMPLATES_AUTO_RELOAD = True


class TestingConfig(AppConfig):
    TESTING = True

    APP_ROOT = "./approot"
    DB_ROOT = os.path.join(APP_ROOT, "db")

    MONGO_URI = "mongodb://localhost:27017/otterdog"


validate_required_settings(TestingConfig)


# Load all possible configurations
config_dict = {"Production": ProductionConfig, "Debug": DebugConfig}
