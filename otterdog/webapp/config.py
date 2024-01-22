#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the MIT License
#  which is available at https://spdx.org/licenses/MIT.html
#  SPDX-License-Identifier: MIT
#  *******************************************************************************

import os
from decouple import config  # type: ignore


class AppConfig(object):
    QUART_APP = "otterdog.webapp"

    # Set up the App SECRET_KEY
    SECRET_KEY = config("SECRET_KEY")

    GITHUB_WEBHOOK_ENDPOINT = config("GITHUB_WEBHOOK_ENDPOINT", default="/github-webhook/receive")
    GITHUB_WEBHOOK_SECRET = config("GITHUB_WEBHOOK_SECRET", default=None)

    APP_ROOT = config("APP_ROOT")

    if not os.path.exists(APP_ROOT):
        os.makedirs(APP_ROOT)

    # GitHub App config
    GITHUB_APP_ID = config('GITHUB_APP_ID')
    GITHUB_APP_PRIVATE_KEY = config('GITHUB_APP_PRIVATE_KEY')


class ProductionConfig(AppConfig):
    DEBUG = False

    # Security
    SESSION_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_DURATION = 3600


class DebugConfig(AppConfig):
    DEBUG = True


# Load all possible configurations
config_dict = {'Production': ProductionConfig, 'Debug': DebugConfig}
