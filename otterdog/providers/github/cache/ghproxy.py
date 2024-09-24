#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from typing import Any

from otterdog.providers.github.cache import CacheStrategy


def ghproxy_cache(uri: str) -> CacheStrategy:
    return _GHProxy(uri)


class _GHProxy(CacheStrategy):
    def __init__(self, proxy_uri: str):
        self._proxy_uri = proxy_uri

    def get_cache_backend(self) -> None:
        return None

    def is_external(self) -> bool:
        return True

    def get_request_parameters(self) -> dict[str, Any]:
        return {"proxy": self._proxy_uri, "ssl": False}
