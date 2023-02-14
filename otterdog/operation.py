# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

from abc import abstractmethod
from typing import Protocol

from config import OtterdogConfig, OrganizationConfig
from utils import IndentingPrinter


class Operation(Protocol):
    @abstractmethod
    def init(self, config: OtterdogConfig, printer: IndentingPrinter) -> None: raise NotImplementedError

    @abstractmethod
    def execute(self, org_config: OrganizationConfig) -> int: raise NotImplementedError
