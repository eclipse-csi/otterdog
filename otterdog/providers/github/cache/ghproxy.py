#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

from typing import TYPE_CHECKING

from . import CacheStrategy

if TYPE_CHECKING:
    from typing import Any


def ghproxy_cache(uri: str) -> CacheStrategy:
    return _GHProxy(uri)


class _GHProxy(CacheStrategy):
    def __init__(self, proxy_uri: str):
        from urllib import parse

        self._proxy_uri = parse.urlparse(proxy_uri)

    def get_cache_backend(self) -> None:
        return None

    def is_external(self) -> bool:
        return True

    def replace_base_url(self, base_url: str) -> str:
        from urllib import parse

        url = parse.urlparse(base_url)
        return parse.urlunparse(self._proxy_uri._replace(path=url.path))

    def get_request_parameters(self) -> dict[str, Any]:
        return {}

    def __str__(self):
        return f"ghproxy-cache('{self._proxy_uri}')"
