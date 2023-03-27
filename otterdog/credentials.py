# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

from abc import abstractmethod
from typing import Protocol

import mintotp

from . import utils


class Credentials:
    """
    A simple data class to hold credential information to access GitHub.
    """

    def __init__(self, username: str, password: str, github_token: str, totp_secret: str):
        self.username = username
        self.password = password
        self.github_token = github_token
        self._totp_secret = totp_secret

    def get_totp(self) -> str:
        totp = mintotp.totp(self._totp_secret)
        utils.print_trace(f"generated totp '{totp}'")
        return totp

    def __str__(self) -> str:
        return "Credentials(username={})".format(self.username)


class CredentialProvider(Protocol):
    @abstractmethod
    def get_credentials(self, data: dict[str, str]) -> Credentials: raise NotImplementedError

    @abstractmethod
    def get_secret(self, data: str) -> str: raise NotImplementedError
