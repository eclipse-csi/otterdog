#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import asyncio
import logging
import threading

import git
import pytest

from otterdog import jsonnet
from otterdog.jsonnet import JsonnetConfig

_BASE_TEMPLATE = "https://github.com/example/otterdog-defaults#otterdog-defaults.libsonnet@main"
_TEMPLATE_URL = "https://github.com/example/otterdog-defaults#otterdog-defaults.libsonnet@{ref}"


@pytest.fixture
def template_repo(tmp_path, monkeypatch):
    """A local repository of a template with a branch 'main' and a tag 'v1.0.0', cloned instead of github.com."""

    source = tmp_path / "source"
    with git.Repo.init(source, initial_branch="main") as repo:
        (source / "otterdog-defaults.libsonnet").write_text("{}")
        repo.index.add(["otterdog-defaults.libsonnet"])
        author = git.Actor("otterdog", "otterdog@example.org")
        commit = repo.index.commit("initial", author=author, committer=author)
        repo.create_tag("v1.0.0")

    clone_from = git.Repo.clone_from
    monkeypatch.setattr(git.Repo, "clone_from", lambda url, to_path, **kwargs: clone_from(str(source), to_path))
    monkeypatch.setattr(jsonnet, "_reported_branch_templates", set())
    return commit.hexsha


def _update(tmp_path, ref: str, run: int = 0) -> None:
    config = JsonnetConfig("my-org", str(tmp_path / f"run-{run}"), _TEMPLATE_URL.format(ref=ref), False)
    config._update_template_repo(str(tmp_path / "templates" / ref))


def _branch_warnings(caplog) -> list[str]:
    return [
        r.getMessage()
        for r in caplog.records
        if r.levelno == logging.WARNING and "references the branch" in r.getMessage()
    ]


def test_a_template_referencing_a_branch_is_reported_once(template_repo, tmp_path, caplog):
    with caplog.at_level(logging.WARNING):
        # the first run clones the template, the second one pulls the changes of the branch
        _update(tmp_path, "main", 0)
        _update(tmp_path, "main", 1)

    (warning,) = _branch_warnings(caplog)
    assert "'main'" in warning
    assert "tag or a commit SHA" in warning


@pytest.mark.parametrize("ref", ["v1.0.0", "commit"])
def test_a_template_referencing_a_tag_or_a_commit_is_not_reported(template_repo, tmp_path, caplog, ref):
    ref = template_repo if ref == "commit" else ref
    with caplog.at_level(logging.WARNING):
        _update(tmp_path, ref, 0)
        _update(tmp_path, ref, 1)

    assert _branch_warnings(caplog) == []


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
