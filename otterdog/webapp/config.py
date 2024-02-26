#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import os
import random
import string

from decouple import config  # type: ignore


class AppConfig:
    QUART_APP = "otterdog.webapp"

    # Assets Management
    ASSETS_ROOT = config("ASSETS_ROOT", default="/static/assets")

    APP_ROOT = config("APP_ROOT")
    DB_ROOT = os.path.join(APP_ROOT, "db")

    MONGO_URI = config("MONGO_URI", default="mongodb://mongodb:27017/otterdog")
    REDIS_URI = config("REDIS_URI", default="redis://redis:6379")

    OTTERDOG_CONFIG_OWNER = config("OTTERDOG_CONFIG_OWNER", default=None)
    OTTERDOG_CONFIG_REPO = config("OTTERDOG_CONFIG_REPO", default=None)
    OTTERDOG_CONFIG_PATH = config("OTTERDOG_CONFIG_PATH", default=None)
    OTTERDOG_CONFIG_TOKEN = config("OTTERDOG_CONFIG_TOKEN", default=None)

    # Set up the App SECRET_KEY
    SECRET_KEY = config("SECRET_KEY", default=None)
    if not SECRET_KEY:
        SECRET_KEY = "".join(random.choice(string.ascii_lowercase) for i in range(32))

    GITHUB_ADMIN_TEAM = config("GITHUB_ADMIN_TEAM", default="otterdog-admins")
    GITHUB_WEBHOOK_ENDPOINT = config("GITHUB_WEBHOOK_ENDPOINT", default="/github-webhook/receive")
    GITHUB_WEBHOOK_SECRET = config("GITHUB_WEBHOOK_SECRET", default=None)
    GITHUB_WEBHOOK_VALIDATION_CONTEXT = config("GITHUB_WEBHOOK_VALIDATION_CONTEXT", default="otterdog-validate")
    GITHUB_WEBHOOK_SYNC_CONTEXT = config("GITHUB_WEBHOOK_SYNC_CONTEXT", default="otterdog-sync")

    # GitHub App config
    GITHUB_APP_ID = config("GITHUB_APP_ID")
    GITHUB_APP_PRIVATE_KEY = config("GITHUB_APP_PRIVATE_KEY")


class ProductionConfig(AppConfig):
    DEBUG = False

    # Security
    SESSION_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_DURATION = 3600


class DebugConfig(AppConfig):
    DEBUG = True


# Load all possible configurations
config_dict = {"Production": ProductionConfig, "Debug": DebugConfig}
