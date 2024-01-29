#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************
import logging
import os
from sys import exit

from decouple import config  # type: ignore

from otterdog.webapp import create_app
from otterdog.webapp.config import config_dict

# WARNING: Don't run with debug turned on in production!
DEBUG: bool = config("DEBUG", default=True, cast=bool)

# Determine which configuration to use
config_mode = "Debug" if DEBUG else "Production"

try:
    app_config = config_dict[config_mode]
except KeyError:
    exit("Error: Invalid <config_mode>. Expected values [Debug, Production] ")

app = create_app(app_config)  # type: ignore

logging.basicConfig(level=logging.INFO)

if os.path.exists(app_config.APP_ROOT):
    os.chdir(app_config.APP_ROOT)
else:
    app.logger.error(f"APP_ROOT '{app_config.APP_ROOT}' does not exist, exiting.")
    exit(1)

if DEBUG:
    app.logger.info("DEBUG       = " + str(DEBUG))
    app.logger.info("Environment = " + config_mode)
    app.logger.info("QUART_APP   = " + app_config.QUART_APP)
    app.logger.info("APP_ROOT    = " + app_config.APP_ROOT)


def run():
    app.run(debug=True)


if __name__ == "__main__":
    run()
