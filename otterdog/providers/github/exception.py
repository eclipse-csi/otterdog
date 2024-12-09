#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************


class GitHubException(Exception):
    def __init__(self, url: str | None, status: int, data: str):
        self.__url = url
        self.__status = status
        self.__data = data

    @property
    def url(self) -> str | None:
        return self.__url

    @property
    def status(self) -> int:
        return self.__status

    @property
    def data(self) -> str:
        return self.__data

    def __str__(self):
        return f"Exception while accessing '{self.url}': (status={self.status}, body={self.data})"


class BadCredentialsException(Exception):
    def __init__(self, url: str, message: str):
        self.__url = url
        self.__message = message

    @property
    def url(self) -> str:
        return self.__url

    @property
    def message(self) -> str:
        return self.__message

    def __str__(self):
        return f"Bad Credentials while accessing '{self.url}': (message={self.message})"


class InsufficientPermissionsException(Exception):
    def __init__(self, url: str, status: int, message: str, missing_scopes: list[str]):
        self.__url = url
        self.__status = status
        self.__message = message
        self.__missing_scopes = missing_scopes

    @property
    def url(self) -> str:
        return self.__url

    @property
    def status(self) -> int:
        return self.__status

    @property
    def message(self) -> str:
        return self.__message

    @property
    def missing_scopes(self) -> list[str]:
        return self.__missing_scopes

    def __str__(self):
        return f"Insufficient permissions while accessing '{self.url}': " f"(missing scopes={self.missing_scopes})"
