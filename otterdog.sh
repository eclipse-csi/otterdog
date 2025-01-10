#!/usr/bin/env bash
#
#  *******************************************************************************
#  Copyright (c) 2023-2025 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************
#

# resolve the program directory
PRG="$0"
while [ -h "$PRG" ] ; do
  ls=$(ls -ld "$PRG")
  link=$(expr "$ls" : '.*-> \(.*\)$')
  if expr "$link" : '/.*' > /dev/null; then
    PRG="$link"
  else
    PRG=$(dirname "$PRG")/"$link"
  fi
done
PRGDIR=$(dirname "$PRG")

if ! command -v poetry &> /dev/null
then
    # activate virtual environment
    # shellcheck source=/dev/null
    source "$PRGDIR"/.venv/bin/activate
    PYTHONPATH=$PYTHONPATH:$PRGDIR python3 -m otterdog.cli "$@"
else
    poetry -P "$PRGDIR" run otterdog "$@"
fi
