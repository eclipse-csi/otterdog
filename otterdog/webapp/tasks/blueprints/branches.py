#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

"""Helpers to manage the remediation branch `otterdog/blueprint/<id>` of a blueprint."""

from __future__ import annotations

from logging import Logger, getLogger
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from otterdog.providers.github.rest import RestApi

BRANCH_PREFIX = "otterdog/blueprint/"

_logger = getLogger(__name__)


def branch_name_for(blueprint_id: str) -> str:
    return f"{BRANCH_PREFIX}{blueprint_id}"


def blueprint_id_from_branch(branch_name: str) -> str | None:
    """Returns the blueprint id encoded in a remediation branch name, None for any other branch."""
    if branch_name.startswith(BRANCH_PREFIX) and len(branch_name) > len(BRANCH_PREFIX):
        return branch_name[len(BRANCH_PREFIX) :]
    return None


def is_otterdog_commit(commit: dict, bot_login: str) -> bool:
    """
    Commits created by otterdog through the contents API are authored by the GitHub App's bot user,
    e.g. `otterdog[bot]`. Commits of other bots (dependabot, renovate, ...) are not otterdog's.
    """
    author = commit.get("author") or {}
    committer = commit.get("committer") or {}
    return author.get("login") == bot_login or committer.get("login") == bot_login


async def branch_exists(rest_api: RestApi, org_id: str, repo_name: str, branch_name: str) -> bool:
    try:
        await rest_api.reference.get_branch_reference(org_id, repo_name, branch_name)
        return True
    except RuntimeError:
        return False


async def get_default_branch_sha(rest_api: RestApi, org_id: str, repo_name: str, default_branch: str) -> str:
    default_branch_data = await rest_api.reference.get_branch_reference(org_id, repo_name, default_branch)
    return default_branch_data["object"]["sha"]


async def reset_branch_to_default_branch(
    rest_api: RestApi,
    org_id: str,
    repo_name: str,
    branch_name: str,
    default_branch: str,
) -> str:
    """
    Resets the branch onto the head of the default branch, creating it if it does not exist.

    The branch is pointed at an empty commit on top of the default branch instead of its head
    itself: a pull request whose head becomes an ancestor of its base is closed by GitHub, which
    would dismiss the blueprint and delete the branch while it is being rewritten.

    :return: the sha the branch points to afterwards
    """
    default_sha = await get_default_branch_sha(rest_api, org_id, repo_name, default_branch)
    default_commit = await rest_api.commit.get_git_commit(org_id, repo_name, default_sha)
    empty_commit = await rest_api.commit.create_git_commit(
        org_id,
        repo_name,
        f"chore(otterdog): recreate branch {branch_name} from {default_branch}",
        default_commit["tree"]["sha"],
        [default_sha],
    )
    sha = empty_commit["sha"]

    if await branch_exists(rest_api, org_id, repo_name, branch_name):
        await rest_api.reference.update_reference(org_id, repo_name, branch_name, sha, force=True)
    else:
        await rest_api.reference.create_reference(org_id, repo_name, branch_name, sha)

    return sha


async def sync_branch_with_default_branch(
    rest_api: RestApi,
    org_id: str,
    repo_name: str,
    branch_name: str,
    default_branch: str,
    bot_login: str,
    logger: Logger | None = None,
) -> bool:
    """
    Brings an existing remediation branch up to date with the default branch.

    - a branch without own commits, or whose commits were all made by otterdog, is reset to
      the head of the default branch, so stale commits disappear and the files are rewritten
    - a branch carrying commits of maintainers gets the default branch merged in to preserve
      their edits, a conflicting merge is left alone and logged

    :return: True if the branch was reset and all files must be written again
    """
    log = logger if logger is not None else _logger
    comparison = await rest_api.commit.compare(org_id, repo_name, default_branch, branch_name)

    behind_by = comparison.get("behind_by", 0)
    own_commits = comparison.get("commits", [])

    if len(own_commits) == 0:
        # identical to the default branch (or behind it), nothing to preserve
        if behind_by > 0:
            await reset_branch_to_default_branch(rest_api, org_id, repo_name, branch_name, default_branch)
        return True

    if behind_by == 0:
        return False

    if all(is_otterdog_commit(commit, bot_login) for commit in own_commits):
        log.info(
            f"resetting stale branch '{branch_name}' in repo '{org_id}/{repo_name}', "
            f"{behind_by} commit(s) behind '{default_branch}' and only otterdog commits"
        )
        await reset_branch_to_default_branch(rest_api, org_id, repo_name, branch_name, default_branch)
        return True

    merged = await rest_api.repo.merge_branch(
        org_id,
        repo_name,
        branch_name,
        default_branch,
        f"Merge branch '{default_branch}' into {branch_name}",
    )

    if merged is False:
        log.warning(
            f"branch '{branch_name}' in repo '{org_id}/{repo_name}' conflicts with "
            f"'{default_branch}' and carries commits of maintainers, leaving it untouched"
        )

    return False
