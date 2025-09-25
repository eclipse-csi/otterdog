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

from otterdog.logging import init_logging
from otterdog.webapp import create_app
from otterdog.webapp.config import config_dict
from otterdog.webapp.utils import get_temporary_base_directory

# WARNING: Don't run with debug turned on in production!
DEBUG: bool = config("DEBUG", default=True, cast=bool)

# Determine which configuration to use
config_mode = "Debug" if DEBUG else "Production"

try:
    app_config = config_dict[config_mode]
except KeyError:
    exit("Error: Invalid <config_mode>. Expected values [Debug, Production] ")

app = create_app(app_config)  # type: ignore

logging.basicConfig(
    format="[%(asctime)s.%(msecs)03d  ] [%(process)d] [%(levelname)s] %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
)

# logging.getLogger("hypercorn.access").disabled = True

os.makedirs(app_config.APP_ROOT, exist_ok=True)
os.makedirs(app_config.DB_ROOT, exist_ok=True)

tmp_dir = get_temporary_base_directory(app)
os.makedirs(tmp_dir, exist_ok=True)

if os.path.exists(app_config.APP_ROOT):
    os.chdir(app_config.APP_ROOT)
else:
    app.logger.error(f"APP_ROOT '{app_config.APP_ROOT}' does not exist, exiting.")
    exit(1)

if DEBUG:
    from otterdog.cache import get_github_cache

    # enable debug outputs
    init_logging(2, False)

    app.logger.info("DEBUG         = " + str(DEBUG))
    app.logger.info("Environment   = " + config_mode)
    app.logger.info("CACHE_CONTROL = " + app_config.CACHE_CONTROL)
    app.logger.info("QUART_APP     = " + app_config.QUART_APP)
    app.logger.info("APP_ROOT      = " + app_config.APP_ROOT)
    app.logger.info("GH_CACHE      = " + str(get_github_cache()))
    app.logger.info("TMP_DIR       = " + tmp_dir)
else:
    # setup app logging to level INFO
    init_logging(1, False)


def run():
    app.run(debug=True)


if __name__ == "__main__":
    run()
