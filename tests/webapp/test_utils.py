#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from datetime import timedelta

import pytest

from otterdog.webapp.utils import backoff_if_needed, current_utc_time


@pytest.mark.asyncio
async def test_backoff_if_needed():
    # check that we wait the required timeout period
    start = current_utc_time()
    await backoff_if_needed(start, timedelta(seconds=3))
    end = current_utc_time()
    assert end - start > timedelta(seconds=3)

    # check that we do not wait if the required timeout already expired
    start = current_utc_time()
    await backoff_if_needed(start - timedelta(seconds=60), timedelta(seconds=3))
    end = current_utc_time()
    assert end - start < timedelta(seconds=1)
