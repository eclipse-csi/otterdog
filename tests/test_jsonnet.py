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
from otterdog.utils import is_local_template, jsonnet_evaluate_snippet

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


@pytest.mark.parametrize(
    "base_template,expected",
    [
        (_BASE_TEMPLATE, False),
        ("https://github.com/example/otterdog-defaults#otterdog/defaults.libsonnet@v1.0.0", False),
        ("defaults/otterdog-defaults.libsonnet", True),
        ("../shared/otterdog-defaults.libsonnet", True),
        ("/etc/otterdog/otterdog-defaults.libsonnet", True),
        ("~/otterdog-defaults.libsonnet", True),
    ],
)
def test_a_base_template_is_a_url_or_a_local_path(base_template, expected):
    assert is_local_template(base_template) is expected


def _local_template(tmp_path):
    template_dir = tmp_path / "defaults"
    template_dir.mkdir()
    (template_dir / "helper.libsonnet").write_text("{ greeting: 'hello' }")
    (template_dir / "my-defaults.libsonnet").write_text(
        "local helper = import 'helper.libsonnet';\n{ newOrg(name, id):: { name: name, github_id: id, greeting: helper.greeting } }"
    )
    return template_dir / "my-defaults.libsonnet"


@pytest.mark.parametrize("local_mode", [False, True])
async def test_a_local_base_template_is_linked_into_the_vendor_directory(tmp_path, local_mode):
    template_file = _local_template(tmp_path)
    config = JsonnetConfig("my-org", str(tmp_path / "orgs"), str(template_file), local_mode)

    await config.init_template()

    assert config.base_template_repo_name == "defaults"
    assert config.import_statement == "import 'vendor/defaults/my-defaults.libsonnet'"
    assert config.template_dir == str(tmp_path / "orgs" / "my-org" / "vendor" / "defaults")
    assert (tmp_path / "orgs" / "my-org" / "vendor" / "defaults").resolve() == template_file.parent.resolve()
    # the template is evaluated through the vendor directory, including the libraries it imports
    organization = jsonnet_evaluate_snippet(f"(import '{config.template_file}').newOrg('p', 'my-org')")
    assert organization == {"name": "p", "github_id": "my-org", "greeting": "hello"}


async def test_a_local_base_template_is_linked_again_on_every_initialization(tmp_path):
    template_file = _local_template(tmp_path)

    for _ in range(2):
        config = JsonnetConfig("my-org", str(tmp_path / "orgs"), str(template_file), False)
        await config.init_template()

    assert (tmp_path / "orgs" / "my-org" / "vendor" / "defaults" / "my-defaults.libsonnet").is_file()
    # removing the vendor directory never removes the local template
    assert template_file.is_file()


async def test_a_missing_local_base_template_is_reported(tmp_path):
    config = JsonnetConfig("my-org", str(tmp_path / "orgs"), str(tmp_path / "defaults" / "missing.libsonnet"), False)

    with pytest.raises(RuntimeError, match=r"local base template .* does not exist"):
        await config.init_template()


async def test_a_local_base_template_must_not_contain_the_organization_configuration(tmp_path):
    template_file = tmp_path / "my-defaults.libsonnet"
    template_file.write_text("{}")
    config = JsonnetConfig("my-org", str(tmp_path / "orgs"), str(template_file), False)

    with pytest.raises(RuntimeError, match="move the template into a directory of its own"):
        await config.init_template()


def test_a_local_base_template_must_not_be_located_in_the_root_directory(tmp_path):
    with pytest.raises(ValueError, match="root directory"):
        JsonnetConfig("my-org", str(tmp_path / "orgs"), "/my-defaults.libsonnet", False)
