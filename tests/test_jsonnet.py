#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import asyncio
import threading

import pytest

from otterdog import jsonnet
from otterdog.jsonnet import JsonnetConfig

_BASE_TEMPLATE = "https://github.com/example/otterdog-defaults#otterdog-defaults.libsonnet@main"


async def test_a_cancelled_initialization_keeps_the_lock_of_the_templates_until_git_completes(monkeypatch, tmp_path):
    # git runs in a thread, which cannot be stopped when the caller is cancelled, e.g. a request whose client disconnects
    started, release = threading.Event(), threading.Event()

    def update_template_repo(self, template_dir):
        started.set()
        release.wait(10)

    monkeypatch.setattr(JsonnetConfig, "_update_template_repo", update_template_repo)
    config = JsonnetConfig("my-org", str(tmp_path), _BASE_TEMPLATE, False)

    initialization = asyncio.create_task(config.init_template())
    await asyncio.to_thread(started.wait, 10)
    initialization.cancel()
    with pytest.raises(asyncio.CancelledError):
        await initialization

    # other callers cannot update the same cached template meanwhile
    assert jsonnet._template_lock.locked()
    (update,) = jsonnet._template_updates
    release.set()
    await update

    assert not jsonnet._template_lock.locked()
