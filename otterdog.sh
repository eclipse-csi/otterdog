#!/usr/bin/env bash
# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

if ! command -v poetry
then
    # activate virtual environment
    . .venv/bin/activate
    otterdog "$@"
else
    poetry run otterdog "$@"
fi
