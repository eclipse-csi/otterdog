# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

from dataclasses import dataclass, field
from typing import Any

from jsonbender import bend, S, F, Forall

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

    @classmethod
    def from_model(cls, data: dict[str, Any]) -> "GitHubOrganization":
        mapping = {
            "github_id": S("github_id"),
            "settings": S("settings") >> F(lambda x: OrganizationSettings.from_model(x)),
            "webhooks": S("webhooks") >> Forall(lambda x: OrganizationWebhook.from_model(x)),
            "repositories": S("repositories") >> Forall(lambda x: Repository.from_model(x))
        }

        return cls(**bend(mapping, data))
