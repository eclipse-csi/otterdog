# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

import time
from abc import abstractmethod
from typing import Protocol, Optional

import mintotp  # type: ignore

from otterdog import utils


class Credentials:
    """
    A simple data class to hold credential information to access GitHub.
    """

    def __init__(self, username: str, password: str, github_token: str, totp_secret: str):
        self.username = username
        self.password = password
        self.github_token = github_token
        self._totp_secret = totp_secret
        self._last_totp = None

    def get_totp(self) -> str:
        while True:
            totp = mintotp.totp(self._totp_secret)
            utils.print_trace(f"generated totp '{totp}'")

            if self._last_totp is None or totp != self._last_totp:
                self._last_totp = totp
                return totp
            else:
                utils.print_info("waiting 3s till generating new totp ...")
                time.sleep(3)

    def __str__(self) -> str:
        return "Credentials(username={})".format(self.username)


class CredentialProvider(Protocol):
    @abstractmethod
    def get_credentials(self, eclipse_project: Optional[str], data: dict[str, str]) -> Credentials:
        ...

    @abstractmethod
    def get_secret(self, data: str) -> str:
        ...
