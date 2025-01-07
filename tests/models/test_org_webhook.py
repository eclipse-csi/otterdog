#  *******************************************************************************
#  Copyright (c) 2023-2025 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from collections.abc import Mapping
from typing import Any

from otterdog.jsonnet import JsonnetConfig
from otterdog.models import ModelObject
from otterdog.models.organization_webhook import OrganizationWebhook
from otterdog.utils import UNSET, Change, query_json

from . import ModelTest


class OrganizationWebhookTest(ModelTest):
    def create_model(self, data: Mapping[str, Any]) -> ModelObject:
        return OrganizationWebhook.from_model_data(data)

    @property
    def template_function(self) -> str:
        return JsonnetConfig.create_org_webhook

    @property
    def model_data(self):
        return self.load_json_resource("otterdog-webhook.json")

    @property
    def provider_data(self):
        return self.load_json_resource("github-webhook.json")

    def test_load_from_model(self):
        webhook = OrganizationWebhook.from_model_data(self.model_data)

        assert webhook.id is UNSET
        assert webhook.active is True
        assert webhook.events == ["push"]
        assert webhook.content_type == "form"
        assert webhook.secret == "blabla"
        assert webhook.url == "https://www.example.org"
        assert webhook.insecure_ssl == "0"

    def test_load_from_provider(self):
        webhook = OrganizationWebhook.from_provider_data(self.org_id, self.provider_data)

        assert webhook.id == 1
        assert webhook.active is True
        assert webhook.events == ["push", "pull_request"]
        assert webhook.content_type == "json"
        assert webhook.secret is None
        assert webhook.url == "https://www.example.org"
        assert webhook.insecure_ssl == "0"

    async def test_to_provider(self):
        webhook = OrganizationWebhook.from_model_data(self.model_data)

        webhook.secret = UNSET

        provider_data = await webhook.to_provider_data(self.org_id, self.provider)

        assert len(provider_data) == 3
        assert provider_data["active"] is True
        assert provider_data["events"] == ["push"]

        assert query_json("config.secret", provider_data) or "" == ""
        assert query_json("config.url", provider_data) == "https://www.example.org"
        assert query_json("config.insecure_ssl", provider_data) == "0"
        assert query_json("config.content_type", provider_data) == "form"

    async def test_changes_to_provider(self):
        current = OrganizationWebhook.from_model_data(self.model_data)
        other = OrganizationWebhook.from_model_data(self.model_data)

        other.active = False
        other.insecure_ssl = "1"

        changes = current.get_difference_from(other)
        provider_data = await OrganizationWebhook.changes_to_provider(self.org_id, changes, self.provider)

        assert len(provider_data) == 2
        assert provider_data["active"] is True
        assert query_json("config.insecure_ssl", provider_data) == "0"

    def test_patch(self):
        current = OrganizationWebhook.from_model_data(self.model_data)
        default = OrganizationWebhook.from_model_data(self.model_data)

        default.url = "https://www.notexistent.org"
        default.active = False

        patch = current.get_patch_to(default)

        assert len(patch) == 2
        assert patch["url"] == current.url
        assert patch["active"] is current.active

    def test_difference(self):
        current = OrganizationWebhook.from_model_data(self.model_data)
        other = OrganizationWebhook.from_model_data(self.model_data)

        other.active = False
        other.insecure_ssl = "1"

        diff = current.get_difference_from(other)

        assert len(diff) == 2
        assert diff["active"] == Change(other.active, current.active)
        assert diff["insecure_ssl"] == Change(other.insecure_ssl, current.insecure_ssl)
