# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

import os

from dataclasses import dataclass, field
from typing import Any

from jsonbender import bend, S, F, Forall

from otterdog.config import OtterdogConfig
import otterdog.utils as utils

from . import is_unset, ValidationContext
from .organization_settings import OrganizationSettings
from .organization_webhook import OrganizationWebhook
from .repository import Repository


@dataclass
class GitHubOrganization:
    github_id: str
    settings: OrganizationSettings
    webhooks: list[OrganizationWebhook] = field(default_factory=list)
    repositories: list[Repository] = field(default_factory=list)

    def add_webhook(self, webhook: OrganizationWebhook) -> None:
        self.webhooks.append(webhook)

    def set_webhooks(self, webhooks: list[OrganizationWebhook]) -> None:
        self.webhooks = webhooks

    def add_repository(self, repo: Repository) -> None:
        self.repositories.append(repo)

    def set_repositories(self, repos: list[Repository]) -> None:
        self.repositories = repos

    def validate(self) -> ValidationContext:
        context = ValidationContext()
        self.settings.validate(context, self)

        for webhook in self.webhooks:
            webhook.validate(context, self)

        for repo in self.repositories:
            repo.validate(context, self)

        return context

    @classmethod
    def from_model(cls, data: dict[str, Any]) -> "GitHubOrganization":
        mapping = {
            "github_id": S("github_id"),
            "settings": S("settings") >> F(lambda x: OrganizationSettings.from_model(x)),
            "webhooks": S("webhooks") >> Forall(lambda x: OrganizationWebhook.from_model(x)),
            "repositories": S("repositories") >> Forall(lambda x: Repository.from_model(x))
        }

        return cls(**bend(mapping, data))


def load_github_organization_from_file(github_id: str,
                                       config_file: str,
                                       config: OtterdogConfig,
                                       resolve_secrets: bool = True) -> GitHubOrganization:
    if not os.path.exists(config_file):
        msg = f"configuration file '{config_file}' for organization '{github_id}' does not exist"
        raise RuntimeError(msg)

    utils.print_debug(f"loading configuration for organization {github_id} from file {config_file}")
    data = utils.jsonnet_evaluate_file(config_file)

    org = GitHubOrganization.from_model(data)

    # resolve webhook secrets
    if resolve_secrets:
        for webhook in org.webhooks:
            secret = webhook.secret
            if not is_unset(secret) and secret is not None:
                webhook.secret = config.get_secret(secret)

    return org
