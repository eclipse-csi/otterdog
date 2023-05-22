#!/usr/bin/env bash
# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

# resolve the program directory
PRG="$0"
while [ -h "$PRG" ] ; do
  ls=`ls -ld "$PRG"`
  link=`expr "$ls" : '.*-> \(.*\)$'`
  if expr "$link" : '/.*' > /dev/null; then
    PRG="$link"
  else
    PRG=`dirname "$PRG"`/"$link"
  fi
done
PRGDIR=`dirname "$PRG"`

if ! command -v poetry &> /dev/null
then
    # activate virtual environment
    source $PRGDIR/.venv/bin/activate
    PYTHONPATH=$PYTHONPATH:$PRGDIR python3 -m otterdog.cli "$@"
else
    poetry -C $PRGDIR run otterdog "$@"
fi
