#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import os
from asyncio import Lock, Task, create_task, shield, to_thread
from collections.abc import Iterator
from contextlib import contextmanager
from functools import cached_property
from pathlib import Path
from shutil import ignore_patterns
from typing import Any

import aiofiles.os
import aiofiles.ospath

from .logging import get_logger
from .utils import is_local_template, jsonnet_evaluate_snippet, parse_github_url, parse_template_url

_template_lock = Lock()
# the updates of the cached templates, see JsonnetConfig._init_base_template, referenced until they complete
_template_updates: set[Task] = set()
# the base templates referencing a branch that have been reported, to warn once per process instead of on every use
_reported_branch_templates: set[tuple[str, str]] = set()
_logger = get_logger(__name__)


@contextmanager
def _lock_across_processes(lock_file: str) -> Iterator[None]:
    """Holds an exclusive lock on a file, waiting until the other processes holding it release it."""

    try:
        import fcntl
    except ImportError:
        # not available on Windows, the processes are not synchronized there
        _logger.debug("cannot lock '%s' on this platform, other otterdog processes are not waited for", lock_file)
        yield
        return

    Path(lock_file).parent.mkdir(parents=True, exist_ok=True)
    with open(lock_file, "a") as file:
        # released when the file is closed, also when the process is killed
        fcntl.flock(file, fcntl.LOCK_EX)
        yield


class JsonnetConfig:
    # FIXME: the function names to create resources should not be hard-coded but
    #        rather follow a convention to add new resources more easily.

    create_org = "newOrg"
    create_org_role = "newOrgRole"
    create_org_team = "newTeam"
    create_org_team_sync = "newTeamSync"
    create_org_custom_property = "newCustomProperty"
    create_org_webhook = "newOrgWebhook"
    create_org_secret = "newOrgSecret"
    create_org_dependabot_secret = "newOrgDependabotSecret"
    create_org_codespaces_secret = "newOrgCodespacesSecret"
    create_org_variable = "newOrgVariable"
    create_org_ruleset = "newOrgRuleset"
    create_org_code_security_configuration = "newOrgCodeSecurityConfiguration"
    create_repo = "newRepo"
    extend_repo = "extendRepo"
    create_repo_webhook = "newRepoWebhook"
    create_repo_secret = "newRepoSecret"
    create_repo_dependabot_secret = "newRepoDependabotSecret"
    create_repo_codespaces_secret = "newRepoCodespacesSecret"
    create_repo_variable = "newRepoVariable"
    create_branch_protection_rule = "newBranchProtectionRule"
    create_repo_ruleset = "newRepoRuleset"
    create_environment = "newEnvironment"
    create_environment_secret = "newEnvSecret"
    create_environment_variable = "newEnvVariable"
    create_pull_request = "newPullRequest"
    create_status_checks = "newStatusChecks"
    create_merge_queue = "newMergeQueue"
    create_copilot_code_review = "newCopilotCodeReview"
    create_pattern = "newPattern"
    create_code_scanning = "newCodeScanning"
    create_code_quality = "newCodeQuality"
    create_code_coverage = "newCodeCoverage"
    create_workflows = "newWorkflows"

    def __init__(
        self,
        org_id: str,
        base_dir: str,
        base_template_url: str,
        local_only: bool,
        org_dir: str | None = None,
    ):
        self._org_id = org_id
        self._base_dir = base_dir
        self._base_org_dir = org_dir if org_dir is not None else base_dir

        # the directory of a local base template, None if the base template is located in a GitHub repository
        self._base_template_local_dir: str | None = None

        if is_local_template(base_template_url):
            local_file = Path(base_template_url).expanduser().absolute()
            if len(local_file.parent.name) == 0:
                raise ValueError(f"the local base template must not be located in the root directory: {local_file}")

            self._base_template_local_dir = str(local_file.parent)
            self._base_template_repo_url = ""
            self._base_template_repo_name = local_file.parent.name
            self._base_template_file = local_file.name
            self._base_template_ref = ""
        else:
            repo_url, file, ref = parse_template_url(base_template_url)

            self._base_template_repo_url = repo_url
            self._base_template_repo_name = os.path.basename(repo_url)
            self._base_template_file = file
            self._base_template_ref = ref

        self._local_only = local_only

        self._default_org_config: dict[str, Any] | None = None
        self._default_org_role_config: dict[str, Any] | None = None
        self._default_org_custom_property_config: dict[str, Any] | None = None
        self._default_org_webhook_config: dict[str, Any] | None = None
        self._default_org_secret_config: dict[str, Any] | None = None
        self._default_org_dependabot_secret_config: dict[str, Any] | None = None
        self._default_org_codespaces_secret_config: dict[str, Any] | None = None
        self._default_org_variable_config: dict[str, Any] | None = None
        self._default_org_ruleset_config: dict[str, Any] | None = None
        self._default_org_code_security_configuration_config: dict[str, Any] | None = None
        self._default_repo_config: dict[str, Any] | None = None
        self._default_repo_webhook_config: dict[str, Any] | None = None
        self._default_repo_secret_config: dict[str, Any] | None = None
        self._default_repo_dependabot_secret_config: dict[str, Any] | None = None
        self._default_repo_codespaces_secret_config: dict[str, Any] | None = None
        self._default_repo_variable_config: dict[str, Any] | None = None
        self._default_branch_protection_rule_config: dict[str, Any] | None = None
        self._default_repo_ruleset_config: dict[str, Any] | None = None
        self._default_environment_config: dict[str, Any] | None = None
        self._default_environment_secret_config: dict[str, Any] | None = None
        self._default_environment_variable_config: dict[str, Any] | None = None
        self._default_pull_request_config: dict[str, Any] | None = None
        self._default_status_checks_config: dict[str, Any] | None = None
        self._default_merge_queue_config: dict[str, Any] | None = None
        self._default_copilot_code_review_config: dict[str, Any] | None = None
        self._default_pattern_config: dict[str, Any] | None = None
        self._default_code_scanning_config: dict[str, Any] | None = None
        self._default_code_quality_config: dict[str, Any] | None = None
        self._default_code_coverage_config: dict[str, Any] | None = None
        self._default_workflows_config: dict[str, Any] | None = None

        self._initialized = False

    @property
    def org_id(self) -> str:
        return self._org_id

    async def init_template(self) -> None:
        if self._initialized is True:
            return

        if self._base_template_local_dir is not None:
            # nothing to fetch, so also done in local mode
            await self._init_local_base_template(self._base_template_local_dir)
        elif not self._local_only:
            await self._init_base_template()

        template_file = self.template_file
        _logger.debug("loading template file '%s'", template_file)
        if not await aiofiles.ospath.exists(self.template_file):
            raise RuntimeError(f"template file '{template_file}' does not exist")

        self._initialized = True

    def default_org_config_for_org_id(self, project_name: str, org_id: str) -> dict[str, Any]:
        try:
            # load the default settings for the organization
            snippet = f"(import '{self.template_file}').{self.create_org}('{project_name}', '{org_id}')"
            return jsonnet_evaluate_snippet(snippet)
        except RuntimeError as ex:
            raise RuntimeError(f"failed to get default organization config for org '{org_id}': {ex}") from ex

    @cached_property
    def default_org_config(self) -> dict[str, Any]:
        return self.default_org_config_for_org_id("default", "default")

    @cached_property
    def default_org_role_config(self):
        try:
            # load the default org role config
            org_role_snippet = f"(import '{self.template_file}').{self.create_org_role}('default')"
            return jsonnet_evaluate_snippet(org_role_snippet)
        except RuntimeError:
            _logger.debug("no default org role config found, roles will be skipped")
            return None

    @cached_property
    def default_team_config(self):
        try:
            # load the default team config
            team_snippet = f"(import '{self.template_file}').{self.create_org_team}('default')"
            return jsonnet_evaluate_snippet(team_snippet)
        except RuntimeError:
            _logger.debug("no default team config found, teams will be skipped")
            return None

    @cached_property
    def default_team_sync_config(self):
        try:
            # load the default team sync config
            team_sync_snippet = f"(import '{self.template_file}').{self.create_org_team_sync}('default')"
            return jsonnet_evaluate_snippet(team_sync_snippet)
        except RuntimeError:
            _logger.debug("no default team sync config found, team syncs will be skipped")
            return None

    @cached_property
    def default_org_custom_property_config(self):
        try:
            # load the default org custom property config
            org_custom_property_snippet = (
                f"(import '{self.template_file}').{self.create_org_custom_property}('default')"
            )
            return jsonnet_evaluate_snippet(org_custom_property_snippet)
        except RuntimeError:
            _logger.debug("no default org custom property config found, custom properties will be skipped")
            return None

    @cached_property
    def default_org_webhook_config(self):
        try:
            # load the default org webhook config
            org_webhook_snippet = f"(import '{self.template_file}').{self.create_org_webhook}('default')"
            return jsonnet_evaluate_snippet(org_webhook_snippet)
        except RuntimeError:
            _logger.debug("no default org webhook config found, webhooks will be skipped")
            return None

    @cached_property
    def default_org_secret_config(self):
        try:
            # load the default org secret config
            org_secret_snippet = f"(import '{self.template_file}').{self.create_org_secret}('default')"
            return jsonnet_evaluate_snippet(org_secret_snippet)
        except RuntimeError:
            _logger.debug("no default org secret config found, secrets will be skipped")
            return None

    @cached_property
    def default_org_variable_config(self):
        try:
            # load the default org variable config
            org_variable_snippet = f"(import '{self.template_file}').{self.create_org_variable}('default')"
            return jsonnet_evaluate_snippet(org_variable_snippet)
        except RuntimeError:
            _logger.debug("no default org variable config found, variables will be skipped")
            return None

    @cached_property
    def default_org_dependabot_secret_config(self):
        try:
            snippet = f"(import '{self.template_file}').{self.create_org_dependabot_secret}('default')"
            return jsonnet_evaluate_snippet(snippet)
        except RuntimeError:
            _logger.debug("no default org Dependabot secret config found, secrets will be skipped")
            return None

    @cached_property
    def default_org_codespaces_secret_config(self):
        try:
            snippet = f"(import '{self.template_file}').{self.create_org_codespaces_secret}('default')"
            return jsonnet_evaluate_snippet(snippet)
        except RuntimeError:
            _logger.debug("no default org Codespaces secret config found, secrets will be skipped")
            return None

    @cached_property
    def default_org_ruleset_config(self):
        try:
            # load the default org ruleset config
            org_ruleset_snippet = f"(import '{self.template_file}').{self.create_org_ruleset}('default')"
            return jsonnet_evaluate_snippet(org_ruleset_snippet)
        except RuntimeError:
            _logger.debug("no default org ruleset config found, rulesets will be skipped")
            return None

    @cached_property
    def default_org_code_security_configuration_config(self):
        try:
            # load the default org code security configuration config
            snippet = f"(import '{self.template_file}').{self.create_org_code_security_configuration}('default')"
            return jsonnet_evaluate_snippet(snippet)
        except RuntimeError:
            _logger.debug("no default org code security configuration config found, configurations will be skipped")
            return None

    @cached_property
    def default_repo_config(self):
        try:
            # load the default repo config
            repo_snippet = f"(import '{self.template_file}').{self.create_repo}('default')"
            return jsonnet_evaluate_snippet(repo_snippet)
        except RuntimeError:
            _logger.debug("no default repo config found, repos will be skipped")
            return None

    @cached_property
    def default_repo_webhook_config(self):
        try:
            # load the default repo webhook config
            repo_webhook_snippet = f"(import '{self.template_file}').{self.create_repo_webhook}('default')"
            return jsonnet_evaluate_snippet(repo_webhook_snippet)
        except RuntimeError:
            _logger.debug("no default repo webhook config found, webhooks will be skipped")
            return None

    @cached_property
    def default_repo_secret_config(self):
        try:
            # load the default repo secret config
            repo_secret_snippet = f"(import '{self.template_file}').{self.create_repo_secret}('default')"
            return jsonnet_evaluate_snippet(repo_secret_snippet)
        except RuntimeError:
            _logger.debug("no default repo secret config found, secrets will be skipped")
            return None

    @cached_property
    def default_repo_variable_config(self):
        try:
            # load the default repo variable config
            repo_variable_snippet = f"(import '{self.template_file}').{self.create_repo_variable}('default')"
            return jsonnet_evaluate_snippet(repo_variable_snippet)
        except RuntimeError:
            _logger.debug("no default repo variable config found, variables will be skipped")
            return None

    @cached_property
    def default_repo_dependabot_secret_config(self):
        try:
            snippet = f"(import '{self.template_file}').{self.create_repo_dependabot_secret}('default')"
            return jsonnet_evaluate_snippet(snippet)
        except RuntimeError:
            _logger.debug("no default repo Dependabot secret config found, secrets will be skipped")
            return None

    @cached_property
    def default_repo_codespaces_secret_config(self):
        try:
            snippet = f"(import '{self.template_file}').{self.create_repo_codespaces_secret}('default')"
            return jsonnet_evaluate_snippet(snippet)
        except RuntimeError:
            _logger.debug("no default repo Codespaces secret config found, secrets will be skipped")
            return None

    @cached_property
    def default_branch_protection_rule_config(self):
        try:
            # load the default branch protection rule config
            branch_protection_snippet = (
                f"(import '{self.template_file}').{self.create_branch_protection_rule}('default')"
            )
            return jsonnet_evaluate_snippet(branch_protection_snippet)
        except RuntimeError:
            _logger.debug("no default branch protection rule config found, branch protection rules will be skipped")
            return None

    @cached_property
    def default_repo_ruleset_config(self):
        try:
            # load the default repo ruleset config
            repo_ruleset_snippet = f"(import '{self.template_file}').{self.create_repo_ruleset}('default')"
            return jsonnet_evaluate_snippet(repo_ruleset_snippet)
        except RuntimeError:
            _logger.debug("no default repo ruleset config found, rulesets will be skipped")
            return None

    @cached_property
    def default_environment_config(self):
        try:
            # load the default environment config
            environment_snippet = f"(import '{self.template_file}').{self.create_environment}('default')"
            return jsonnet_evaluate_snippet(environment_snippet)
        except RuntimeError:
            _logger.debug("no default environment config found, environments will be skipped")
            return None

    @cached_property
    def default_environment_secret_config(self):
        try:
            # load the default environment secret config
            environment_secret_snippet = f"(import '{self.template_file}').{self.create_environment_secret}('default')"
            return jsonnet_evaluate_snippet(environment_secret_snippet)
        except RuntimeError:
            _logger.debug("no default environment secret config found, secrets will be skipped")
            return None

    @cached_property
    def default_environment_variable_config(self):
        try:
            # load the default environment variable config
            environment_variable_snippet = (
                f"(import '{self.template_file}').{self.create_environment_variable}('default')"
            )
            return jsonnet_evaluate_snippet(environment_variable_snippet)
        except RuntimeError:
            _logger.debug("no default environment variable config found, variables will be skipped")
            return None

    @cached_property
    def default_pull_request_config(self):
        try:
            # load the default pull request config
            pull_request_snippet = f"(import '{self.template_file}').{self.create_pull_request}()"
            return jsonnet_evaluate_snippet(pull_request_snippet)
        except RuntimeError:
            _logger.debug("no default pull request config found, pull requests will be skipped")
            return None

    @cached_property
    def default_status_checks_config(self):
        try:
            # load the default status check config
            status_checks_snippet = f"(import '{self.template_file}').{self.create_status_checks}()"
            return jsonnet_evaluate_snippet(status_checks_snippet)
        except RuntimeError:
            _logger.debug("no default status checks config found, status checks will be skipped")
            return None

    @cached_property
    def default_merge_queue_config(self):
        try:
            # load the default merge queue config
            merge_queue_snippet = f"(import '{self.template_file}').{self.create_merge_queue}()"
            return jsonnet_evaluate_snippet(merge_queue_snippet)
        except RuntimeError:
            _logger.debug("no default merge queue config found, merge queues will be skipped")
            return None

    @cached_property
    def default_copilot_code_review_config(self):
        try:
            # load the default copilot code review config
            copilot_code_review_snippet = f"(import '{self.template_file}').{self.create_copilot_code_review}()"
            return jsonnet_evaluate_snippet(copilot_code_review_snippet)
        except RuntimeError:
            _logger.debug("no default copilot code review config found, copilot code reviews will be skipped")
            return None

    @cached_property
    def default_pattern_config(self):
        try:
            # load the default pattern config
            pattern_snippet = f"(import '{self.template_file}').{self.create_pattern}()"
            return jsonnet_evaluate_snippet(pattern_snippet)
        except RuntimeError:
            _logger.debug("no default pattern config found, patterns will be skipped")
            return None

    @cached_property
    def default_code_scanning_config(self):
        try:
            # load the default code scanning config
            code_scanning_snippet = f"(import '{self.template_file}').{self.create_code_scanning}()"
            return jsonnet_evaluate_snippet(code_scanning_snippet)
        except RuntimeError:
            _logger.debug("no default code scanning config found, code scanning will be skipped")
            return None

    @cached_property
    def default_code_quality_config(self):
        try:
            # load the default code quality config
            code_quality_snippet = f"(import '{self.template_file}').{self.create_code_quality}()"
            return jsonnet_evaluate_snippet(code_quality_snippet)
        except RuntimeError:
            _logger.debug("no default code quality config found, code quality will be skipped")
            return None

    @cached_property
    def default_code_coverage_config(self):
        try:
            # load the default code coverage config
            code_coverage_snippet = f"(import '{self.template_file}').{self.create_code_coverage}()"
            return jsonnet_evaluate_snippet(code_coverage_snippet)
        except RuntimeError:
            _logger.debug("no default code coverage config found, code coverage will be skipped")
            return None

    @cached_property
    def default_workflows_config(self):
        try:
            # load the default workflows config
            workflows_snippet = f"(import '{self.template_file}').{self.create_workflows}()"
            return jsonnet_evaluate_snippet(workflows_snippet)
        except RuntimeError:
            _logger.debug("no default workflows config found, workflows will be skipped")
            return None

    @property
    def base_template_repo_name(self) -> str:
        return self._base_template_repo_name

    @property
    def base_template_file_name(self) -> str:
        return self._base_template_file

    @property
    def template_dir(self) -> str:
        return os.path.join(
            self.org_dir,
            "vendor",
            self._base_template_repo_name,
        )

    @property
    def template_file(self) -> str:
        return os.path.join(
            self.template_dir,
            self._base_template_file,
        )

    async def jsonnet_template_files(self):
        """Yield library paths from the whole template checkout, including subdirectories.

        The selected template may import sibling or nested libraries. Return paths
        under the repository root so callers can preserve those import relationships.
        """
        for file in sorted(Path(self.template_dir).rglob("*.libsonnet")):
            yield str(file)

    @property
    def base_dir(self) -> str:
        return self._base_dir

    @property
    def base_org_dir(self) -> str:
        return self._base_org_dir

    @property
    def org_dir(self) -> str:
        return f"{self.base_org_dir}/{self.org_id}"

    @property
    def org_config_file(self) -> str:
        return f"{self.org_dir}/{self.org_id}.jsonnet"

    @property
    def import_statement(self) -> str:
        return f"import 'vendor/{self._base_template_repo_name}/{self._base_template_file}'"

    async def _init_local_base_template(self, local_dir: str) -> None:
        """Links the directory of the local base template as the vendor directory of the organization."""
        from aiofiles.os import makedirs, symlink
        from aiofiles.ospath import exists
        from aioshutil import rmtree

        local_file = Path(local_dir) / self._base_template_file
        if not await exists(local_file):
            raise RuntimeError(f"local base template '{local_file}' does not exist")

        if Path(self.org_dir).resolve().is_relative_to(Path(local_dir).resolve()):
            raise RuntimeError(
                f"the directory '{local_dir}' of the local base template contains the configuration of "
                f"organization '{self.org_id}', move the template into a directory of its own"
            )

        _logger.debug("linking local base template '%s'", local_file)

        if await exists(f"{self.org_dir}/vendor"):
            await rmtree(f"{self.org_dir}/vendor")

        await makedirs(os.path.dirname(self.template_dir))
        await symlink(local_dir, self.template_dir, target_is_directory=True)

    async def _init_base_template(self) -> None:
        from aiofiles.os import makedirs
        from aiofiles.ospath import exists
        from aioshutil import copytree, rmtree

        _logger.debug("initializing base template '%s@%s'", self._base_template_repo_url, self._base_template_ref)
        template_owner, template_repository = parse_github_url(self._base_template_repo_url)

        # cache the template repo with the requested ref in the 'templates' directory
        template_dir = f"{self.base_dir}/templates/{template_owner}/{template_repository}/{self._base_template_ref}"
        # the update runs in its own task, shielded from the cancellation of its caller, e.g. a request whose client
        # disconnects: its git operation in a thread cannot be stopped, so it keeps the lock until it completes
        update = create_task(self._update_template_repo_with_lock(template_dir))
        _template_updates.add(update)
        update.add_done_callback(_template_updates.discard)
        await shield(update)

        # create base directory if it does not exist yet
        if not await exists(self.org_dir):
            await makedirs(self.org_dir)

        if await exists(f"{self.org_dir}/vendor"):
            await rmtree(f"{self.org_dir}/vendor")

        # copy over the cloned template repository
        base_template_directory = os.path.dirname(self.base_template_file_name)
        if len(base_template_directory) > 0:
            selected_directory = Path(template_dir) / base_template_directory

            def _ignore_outside_template_directory(path, names):
                # Keep the selected directory's entire subtree, including deeply
                # nested helpers. Keep its ancestors too, so copytree can reach it.
                ignored_names = []
                for name in names:
                    candidate = Path(path) / name
                    if not candidate.is_relative_to(selected_directory) and not selected_directory.is_relative_to(
                        candidate
                    ):
                        ignored_names.append(name)
                return ignored_names

            ignore = _ignore_outside_template_directory
        else:
            ignore = ignore_patterns(".git")
        await copytree(template_dir, self.template_dir, ignore=ignore)

    async def _update_template_repo_with_lock(self, template_dir: str) -> None:
        async with _template_lock:
            # git waits for the network, run apart to not block the other tasks, e.g. the requests of the webapp
            await to_thread(self._update_template_repo, template_dir)

    def _update_template_repo(self, template_dir: str) -> None:
        """Clones the repository of the base template at its ref in a directory, or pulls its changes from a branch."""

        import git

        # _template_lock only holds within this process: other otterdog processes using the same directory, e.g. several
        # otterdog plan commands running in parallel, would clone the template or pull its changes at once and fail
        with _lock_across_processes(f"{template_dir}.lock"):
            if not os.path.exists(f"{template_dir}/.git"):
                _logger.debug("cloning base template from url '%s'", self._base_template_repo_url)
                with git.Repo.clone_from(self._base_template_repo_url, template_dir) as repo:
                    repo.git.checkout(self._base_template_ref)
                    references_branch = not repo.head.is_detached
            else:
                with git.Repo(template_dir) as repo:
                    # a tag or a commit is checked out as a detached head and never pulled again
                    references_branch = not repo.head.is_detached
                    if references_branch:
                        _logger.debug(
                            "pulling changes from base template url '%s' with ref '%s'",
                            self._base_template_repo_url,
                            repo.head.ref,
                        )
                        repo.remotes.origin.pull()

        if references_branch:
            self._warn_about_branch_reference()

    def _warn_about_branch_reference(self) -> None:
        # the content of a branch, including the python scripts of the template that otterdog executes,
        # changes with every push to it, see docs/threat-model.md
        template = (self._base_template_repo_url, self._base_template_ref)
        if template in _reported_branch_templates:
            return

        _reported_branch_templates.add(template)
        _logger.warning(
            "base template '%s' references the branch '%s': every push to it changes the default configuration and "
            "the python scripts that otterdog executes from it, reference a tag or a commit SHA instead",
            *template,
        )

    def __repr__(self) -> str:
        return f"JsonnetConfig('{self.base_dir}, '{self._base_template_file}')"
