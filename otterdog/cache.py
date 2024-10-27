#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

from typing import TYPE_CHECKING

from otterdog.providers.github.cache.file import file_cache
from otterdog.utils import print_trace

if TYPE_CHECKING:
    from otterdog.providers.github.cache import CacheStrategy

_GITHUB_CACHE = file_cache()


def get_github_cache() -> CacheStrategy:
    global _GITHUB_CACHE

    print_trace(f"Using {_GITHUB_CACHE} as GitHub cache strategy")
    return _GITHUB_CACHE


def set_github_cache(cache: CacheStrategy) -> None:
    global _GITHUB_CACHE

    print_trace(f"Setting {cache} as GitHub cache strategy")
    _GITHUB_CACHE = cache
