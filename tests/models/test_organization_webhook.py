#  *******************************************************************************
#  Copyright (c) 2023 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the MIT License
#  which is available at https://spdx.org/licenses/MIT.html
#  SPDX-License-Identifier: MIT
#  *******************************************************************************

from otterdog.utils import UNSET
from otterdog.models import Diff
from otterdog.models.organization_webhook import OrganizationWebhook

from . import ModelTest


class OrganizationWebhookTest(ModelTest):
    @property
    def model_data(self):
        return self.load_json_resource("otterdog-webhook.json")

    @property
    def provider_data(self):
        return self.load_json_resource("github-webhook.json")

    def test_load_from_model(self):
        webhook = OrganizationWebhook.from_model(self.model_data)

        assert webhook.id is UNSET
        assert webhook.active is True
        assert webhook.events == ["push"]
        assert webhook.content_type == "form"
        assert webhook.secret == "blabla"
        assert webhook.url == "https://www.example.org"
        assert webhook.insecure_ssl == "0"

    def test_load_from_provider(self):
        webhook = OrganizationWebhook.from_provider(self.provider_data)

        assert webhook.id == 1
        assert webhook.active is True
        assert webhook.events == ["push", "pull_request"]
        assert webhook.content_type == "json"
        assert webhook.secret is UNSET
        assert webhook.url == "https://www.example.org"
        assert webhook.insecure_ssl == "0"

    def test_patch(self):
        current = OrganizationWebhook.from_model(self.model_data)

        default = OrganizationWebhook.from_model(self.model_data)

        default.url = "https://www.notexistent.org"
        default.active = False

        patch = current.get_patch_to(default)

        assert len(patch) == 2
        assert patch["url"] == current.url
        assert patch["active"] is current.active

    def test_difference(self):
        current = OrganizationWebhook.from_model(self.model_data)
        other = OrganizationWebhook.from_model(self.model_data)

        other.active = False
        other.insecure_ssl = "1"

        diff = current.get_difference_to(other)

        assert len(diff) == 2
        assert diff["active"] == Diff(current.active, other.active)
        assert diff["insecure_ssl"] == Diff(current.insecure_ssl, other.insecure_ssl)

