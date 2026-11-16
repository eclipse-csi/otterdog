#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import asyncio

import pytest

from otterdog.webapp.lease import RedisLease


async def test_a_lease_is_held_by_a_single_holder(fake_redis):
    first = RedisLease("key", 300)
    second = RedisLease("key", 300)

    assert await first.acquire() is True
    assert await second.acquire() is False
    assert fake_redis.ttls["key"] == 300

    await first.release()

    assert await second.acquire() is True


async def test_a_lease_is_only_released_by_its_holder(fake_redis):
    """The lease of a stalled holder may have expired and been taken over meanwhile."""
    holder = RedisLease("key", 300)
    stalled = RedisLease("key", 300)
    await holder.acquire()

    await stalled.release()
    await stalled.renew()

    assert "key" in fake_redis.values
    assert fake_redis.renewals == 0


async def test_a_held_lease_is_renewed_and_released_afterward(fake_redis):
    lease = RedisLease("key", 1)
    await lease.acquire()

    async with lease.held():
        await asyncio.sleep(0.45)
        assert fake_redis.renewals == 1

    assert "key" not in fake_redis.values

    # the renewal stopped along with the block
    await asyncio.sleep(0.4)
    assert fake_redis.renewals == 1


async def test_a_held_lease_is_released_when_the_block_fails(fake_redis):
    lease = RedisLease("key", 300)
    await lease.acquire()

    async def fail_while_held() -> None:
        async with lease.held():
            raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        await fail_while_held()

    assert "key" not in fake_redis.values
