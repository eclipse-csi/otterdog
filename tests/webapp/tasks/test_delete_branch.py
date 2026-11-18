#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import logging

from pretend import stub

from otterdog.webapp.tasks.delete_branch import DeleteBranchTask


def _task(monkeypatch, delete_reference) -> DeleteBranchTask:
    task = DeleteBranchTask(1, "org", ".eclipsefdn", "otterdog/update")
    monkeypatch.setattr(task, "create_task_model", lambda: None)

    async def rest_api():
        return stub(reference=stub(delete_reference=delete_reference))

    monkeypatch.setattr(DeleteBranchTask, "rest_api", property(lambda _: rest_api()))
    return task


async def test_a_branch_already_deleted_is_not_reported_as_deleted(monkeypatch, caplog):
    async def delete_reference(org_id, repo_name, ref):
        return False

    caplog.set_level(logging.DEBUG, logger="otterdog.webapp.tasks")

    assert await _task(monkeypatch, delete_reference).execute() is None
    assert "deleted branch" not in caplog.text


async def test_a_failed_deletion_fails_the_task(monkeypatch, caplog):
    error = RuntimeError("failed deleting reference 'otterdog/update' in repo 'org/.eclipsefdn'\n422: {}")

    async def delete_reference(org_id, repo_name, ref):
        raise error

    assert await _task(monkeypatch, delete_reference).execute() is error
    assert "failed to execute task" in caplog.text
