# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

from .organization_webhook import OrganizationWebhook


class GitHubOrganization:
    def __init__(self):
        self._webhooks = []

    @property
    def webhooks(self) -> list[OrganizationWebhook]:
        return self._webhooks

    def add_webhook(self, webhook: OrganizationWebhook) -> None:
        self.webhooks.append(webhook)

    def set_webhooks(self, webhooks: list[OrganizationWebhook]) -> None:
        self._webhooks = webhooks
