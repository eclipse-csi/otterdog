#  *******************************************************************************
#  Copyright (c) 2023 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the MIT License
#  which is available at https://spdx.org/licenses/MIT.html
#  SPDX-License-Identifier: MIT
#  *******************************************************************************

class GitHubException(Exception):
    def __init__(self, url: str, status: int, data: str, headers: dict[str, str]):
        self.__url = url
        self.__status = status
        self.__data = data
        self.__headers = headers

    @property
    def url(self) -> str:
        return self.__url

    @property
    def status(self) -> int:
        return self.__status

    @property
    def data(self) -> str:
        return self.__data

    @property
    def headers(self) -> dict[str, str]:
        return self.__headers

    def __str__(self):
        return f"Exception while accessing {self.url}: (status={self.status}, body={self.data})"


class BadCredentialsException(GitHubException):
    def __str__(self):
        return f"Bad Credentials while accessing {self.url}: (body={self.data})"
