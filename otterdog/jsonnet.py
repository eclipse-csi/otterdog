#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import os
from asyncio import Lock
from functools import cached_property
from shutil import ignore_patterns
from typing import Any

import aiofiles.os
import aiofiles.ospath

from .utils import (
    jsonnet_evaluate_snippet,
    parse_github_url,
    parse_template_url,
    print_debug,
)

_template_lock = Lock()


class JsonnetConfig:
    # FIXME: the function names to create resources should not be hard-coded but
    #        rather follow a convention to add new resources more easily.

    create_org = "newOrg"
    create_org_custom_property = "newCustomProperty"
    create_org_webhook = "newOrgWebhook"
    create_org_secret = "newOrgSecret"
    create_org_variable = "newOrgVariable"
    create_repo = "newRepo"
    extend_repo = "extendRepo"
    create_repo_webhook = "newRepoWebhook"
    create_repo_secret = "newRepoSecret"
    create_repo_variable = "newRepoVariable"
    create_branch_protection_rule = "newBranchProtectionRule"
    create_repo_ruleset = "newRepoRuleset"
    create_environment = "newEnvironment"
    create_pull_request = "newPullRequest"
    create_status_checks = "newStatusChecks"
    create_merge_queue = "newMergeQueue"

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

        repo_url, file, ref = parse_template_url(base_template_url)

        self._base_template_repo_url = repo_url
        self._base_template_repo_name = os.path.basename(repo_url)
        self._base_template_file = file
        self._base_template_ref = ref

        self._local_only = local_only

        self._default_org_config: dict[str, Any] | None = None
        self._default_org_custom_property_config: dict[str, Any] | None = None
        self._default_org_webhook_config: dict[str, Any] | None = None
        self._default_org_secret_config: dict[str, Any] | None = None
        self._default_org_variable_config: dict[str, Any] | None = None
        self._default_repo_config: dict[str, Any] | None = None
        self._default_repo_webhook_config: dict[str, Any] | None = None
        self._default_repo_secret_config: dict[str, Any] | None = None
        self._default_repo_variable_config: dict[str, Any] | None = None
        self._default_branch_protection_rule_config: dict[str, Any] | None = None
        self._default_repo_ruleset_config: dict[str, Any] | None = None
        self._default_environment_config: dict[str, Any] | None = None
        self._default_pull_request_config: dict[str, Any] | None = None
        self._default_status_checks_config: dict[str, Any] | None = None
        self._default_merge_queue_config: dict[str, Any] | None = None

        self._initialized = False

    @property
    def org_id(self) -> str:
        return self._org_id

    async def init_template(self) -> None:
        if self._initialized is True:
            return

        if not self._local_only:
            await self._init_base_template()

        template_file = self.template_file
        print_debug(f"loading template file '{template_file}'")
        if not await aiofiles.ospath.exists(self.template_file):
            raise RuntimeError(f"template file '{template_file}' does not exist")

        self._initialized = True

    def default_org_config_for_org_id(self, org_id: str) -> dict[str, Any]:
        try:
            # load the default settings for the organization
            snippet = f"(import '{self.template_file}').{self.create_org}('{org_id}')"
            return jsonnet_evaluate_snippet(snippet)
        except RuntimeError as ex:
            raise RuntimeError(f"failed to get default organization config for org '{org_id}': {ex}") from ex

    @cached_property
    def default_org_config(self) -> dict[str, Any]:
        return self.default_org_config_for_org_id("default")

    @cached_property
    def default_org_custom_property_config(self):
        try:
            # load the default org custom property config
            org_custom_property_snippet = (
                f"(import '{self.template_file}').{self.create_org_custom_property}('default')"
            )
            return jsonnet_evaluate_snippet(org_custom_property_snippet)
        except RuntimeError:
            print_debug("no default org custom property config found, custom properties will be skipped")
            return None

    @cached_property
    def default_org_webhook_config(self):
        try:
            # load the default org webhook config
            org_webhook_snippet = f"(import '{self.template_file}').{self.create_org_webhook}('default')"
            return jsonnet_evaluate_snippet(org_webhook_snippet)
        except RuntimeError:
            print_debug("no default org webhook config found, webhooks will be skipped")
            return None

    @cached_property
    def default_org_secret_config(self):
        try:
            # load the default org secret config
            org_secret_snippet = f"(import '{self.template_file}').{self.create_org_secret}('default')"
            return jsonnet_evaluate_snippet(org_secret_snippet)
        except RuntimeError:
            print_debug("no default org secret config found, secrets will be skipped")
            return None

    @cached_property
    def default_org_variable_config(self):
        try:
            # load the default org variable config
            org_variable_snippet = f"(import '{self.template_file}').{self.create_org_variable}('default')"
            return jsonnet_evaluate_snippet(org_variable_snippet)
        except RuntimeError:
            print_debug("no default org variable config found, variables will be skipped")
            return None

    @cached_property
    def default_repo_config(self):
        try:
            # load the default repo config
            repo_snippet = f"(import '{self.template_file}').{self.create_repo}('default')"
            return jsonnet_evaluate_snippet(repo_snippet)
        except RuntimeError:
            print_debug("no default repo config found, repos will be skipped")
            return None

    @cached_property
    def default_repo_webhook_config(self):
        try:
            # load the default repo webhook config
            repo_webhook_snippet = f"(import '{self.template_file}').{self.create_repo_webhook}('default')"
            return jsonnet_evaluate_snippet(repo_webhook_snippet)
        except RuntimeError:
            print_debug("no default repo webhook config found, webhooks will be skipped")
            return None

    @cached_property
    def default_repo_secret_config(self):
        try:
            # load the default repo secret config
            repo_secret_snippet = f"(import '{self.template_file}').{self.create_repo_secret}('default')"
            return jsonnet_evaluate_snippet(repo_secret_snippet)
        except RuntimeError:
            print_debug("no default repo secret config found, secrets will be skipped")
            return None

    @cached_property
    def default_repo_variable_config(self):
        try:
            # load the default repo variable config
            repo_variable_snippet = f"(import '{self.template_file}').{self.create_repo_variable}('default')"
            return jsonnet_evaluate_snippet(repo_variable_snippet)
        except RuntimeError:
            print_debug("no default repo variable config found, variables will be skipped")
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
            print_debug("no default branch protection rule config found, branch protection rules will be skipped")
            return None

    @cached_property
    def default_repo_ruleset_config(self):
        try:
            # load the default repo ruleset config
            repo_ruleset_snippet = f"(import '{self.template_file}').{self.create_repo_ruleset}('default')"
            return jsonnet_evaluate_snippet(repo_ruleset_snippet)
        except RuntimeError:
            print_debug("no default repo ruleset config found, rulesets will be skipped")
            return None

    @cached_property
    def default_environment_config(self):
        try:
            # load the default environment config
            environment_snippet = f"(import '{self.template_file}').{self.create_environment}('default')"
            return jsonnet_evaluate_snippet(environment_snippet)
        except RuntimeError:
            print_debug("no default environment config found, environments will be skipped")
            return None

    @cached_property
    def default_pull_request_config(self):
        try:
            # load the default pull request config
            pull_request_snippet = f"(import '{self.template_file}').{self.create_pull_request}()"
            return jsonnet_evaluate_snippet(pull_request_snippet)
        except RuntimeError:
            print_debug("no default pull request config found, pull requests will be skipped")
            return None

    @cached_property
    def default_status_checks_config(self):
        try:
            # load the default status check config
            status_checks_snippet = f"(import '{self.template_file}').{self.create_status_checks}()"
            return jsonnet_evaluate_snippet(status_checks_snippet)
        except RuntimeError:
            print_debug("no default status checks config found, status checks will be skipped")
            return None

    @cached_property
    def default_merge_queue_config(self):
        try:
            # load the default merge queue config
            merge_queue_snippet = f"(import '{self.template_file}').{self.create_merge_queue}()"
            return jsonnet_evaluate_snippet(merge_queue_snippet)
        except RuntimeError:
            print_debug("no default merge queue config found, merge queues will be skipped")
            return None

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
        import os

        import aiofiles

        for file in await aiofiles.os.listdir(self.template_dir):
            if file.endswith(".libsonnet"):
                yield os.path.join(self.template_dir, file)

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

    async def _init_base_template(self) -> None:
        import git
        from aiofiles.os import makedirs
        from aiofiles.ospath import exists
        from aioshutil import copytree, rmtree

        print_debug(f"initializing base template '{self._base_template_repo_url}@{self._base_template_ref}'")

        template_owner, template_repository = parse_github_url(self._base_template_repo_url)

        async with _template_lock:
            # cache the template repo with the requested ref in the 'templates' directory
            template_dir = f"{self.base_dir}/templates/{template_owner}/{template_repository}/{self._base_template_ref}"

            if not await exists(f"{template_dir}/.git"):
                print_debug(f"cloning base template from url '{self._base_template_repo_url}'")
                repo = git.Repo.clone_from(self._base_template_repo_url, template_dir)
                repo.git.checkout(self._base_template_ref)
            else:
                repo = git.Repo(template_dir)
                if not repo.head.is_detached:
                    print_debug(
                        f"pulling changes from base template url '{self._base_template_repo_url}' "
                        f"for ref '{repo.head.ref}'"
                    )
                    repo.remotes.origin.pull()

        # create base directory if it does not exist yet
        if not await exists(self.org_dir):
            await makedirs(self.org_dir)

        if await exists(f"{self.org_dir}/vendor"):
            await rmtree(f"{self.org_dir}/vendor")

        # copy over the cloned template repository
        await copytree(template_dir, self.template_dir, ignore=ignore_patterns(".git"))

    def __repr__(self) -> str:
        return f"JsonnetConfig('{self.base_dir}, '{self._base_template_file}')"
