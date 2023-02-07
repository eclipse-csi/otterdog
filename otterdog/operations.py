#  *******************************************************************************
#  Copyright (c) 2023 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the MIT License
#  which is available at https://spdx.org/licenses/MIT.html
#  SPDX-License-Identifier: MIT
#  *******************************************************************************

from abc import abstractmethod
from typing import Protocol

from jsonnet_config import JsonnetConfig


class Operation(Protocol):
    @abstractmethod
    def execute(self, org_id: str, config: JsonnetConfig) -> int: raise NotImplementedError
