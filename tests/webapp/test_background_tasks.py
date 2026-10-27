#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import asyncio

from otterdog.webapp.tasks import Task


class _RecordingTask(Task[None]):
    def __init__(self, executed: list[str]):
        self.executed = executed

    async def _execute(self) -> None:
        self.executed.append("task")

    def __repr__(self) -> str:
        return "_RecordingTask()"


async def test_background_task_objects_are_executed(app):
    """
    Tasks are scheduled as callable objects, the webhook handlers relying on them being awaited.
    """

    executed: list[str] = []

    async with app.app_context():
        app.add_background_task(_RecordingTask(executed))

    await asyncio.gather(*app.background_tasks)

    assert executed == ["task"]


async def test_background_functions_are_executed(app):
    executed: list[str] = []

    async def coroutine_function() -> None:
        executed.append("async")

    def function() -> None:
        executed.append("sync")

    async with app.app_context():
        app.add_background_task(coroutine_function)
        app.add_background_task(function)

    await asyncio.gather(*app.background_tasks)

    assert sorted(executed) == ["async", "sync"]
