#  *******************************************************************************
#  Copyright (c) 2023 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the MIT License
#  which is available at https://spdx.org/licenses/MIT.html
#  SPDX-License-Identifier: MIT
#  *******************************************************************************

from otterdog.utils import UNSET
from otterdog.models.organization_webhook import OrganizationWebhook


def test_load_webhook_from_model(otterdog_webhook_data):
    webhook = OrganizationWebhook.from_model(otterdog_webhook_data)

    assert webhook.id is UNSET
    assert webhook.active is True
    assert webhook.events == ["push"]
    assert webhook.content_type == "form"
    assert webhook.secret == "blabla"
    assert webhook.url == "https://www.example.org"
    assert webhook.insecure_ssl == "0"


def test_load_webhook_from_provider(github_webhook_data):
    webhook = OrganizationWebhook.from_provider(github_webhook_data)

    assert webhook.id == 1
    assert webhook.active is True
    assert webhook.events == ["push", "pull_request"]
    assert webhook.content_type == "json"
    assert webhook.secret is UNSET
    assert webhook.url == "https://www.example.org"
    assert webhook.insecure_ssl == "0"
