#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the MIT License
#  which is available at https://spdx.org/licenses/MIT.html
#  SPDX-License-Identifier: MIT
#  *******************************************************************************

from typing import Optional


class GitHubException(Exception):
    def __init__(self, url: Optional[str], status: int, data: str):
        self.__url = url
        self.__status = status
        self.__data = data

    @property
    def url(self) -> Optional[str]:
        return self.__url

    @property
    def status(self) -> int:
        return self.__status

    @property
    def data(self) -> str:
        return self.__data

    def __str__(self):
        return f"Exception while accessing {self.url}: (status={self.status}, body={self.data})"


class BadCredentialsException(GitHubException):
    def __str__(self):
        return f"Bad Credentials while accessing {self.url}: (body={self.data})"
