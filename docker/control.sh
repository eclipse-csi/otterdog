#!/bin/bash

#
#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************
#

set -e

project=otterdog

printHelp () {
	echo "Usage: control.sh <command>"
	echo "Available commands:"
	echo
	echo "   start         Stops the services, pulls changes, builds docker image(s), "
	echo "                 and starts the services (mongodb, quart)."
	echo "   startdev      Stops and starts the services (mongodb, quart)."
  echo "   build         Pulls changes, builds docker image(s)."
	echo
	echo "   stop          Stops the services."
	echo
	echo "   logs          Tail -f services' logs."
	echo
	echo "   shell         Opens a shell into the webapp container."
}

dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null && pwd )"
pushd "$dir" > /dev/null

case "$1" in
start)
	docker compose -p $project -f docker-compose.base.yml down -t 1
	docker compose -p $project -f docker-compose.base.yml -f docker-compose.prod.yml build
	docker compose -p $project -f docker-compose.base.yml -f docker-compose.prod.yml up -d
	;;
build)
	docker compose -p $project -f docker-compose.base.yml -f docker-compose.dev.yml build --build-arg version="$(poetry version -s)"
	;;
startdev)
	docker compose -p $project -f docker-compose.base.yml down -t 1
	docker compose -p $project -f docker-compose.base.yml -f docker-compose.dev.yml up
	;;
stop)
	docker compose -p $project -f docker-compose.base.yml down -t 1
	;;
shell)
	docker exec -it ${project}-webapp-1 bash
	;;
logs)
	docker compose -p $project -f docker-compose.base.yml logs -f
	;;
*)
	echo "Invalid command $1"
	printHelp
	;;
esac

popd > /dev/null
