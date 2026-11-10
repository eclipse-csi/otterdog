#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

"""End to end tests of the pass and bitwarden credential providers against fake executables.

Fake 'pass' and 'bw' executables placed in PATH record the arguments they receive. They allow to verify,
without mocking the process execution, that:
- shell metacharacters in credential identifiers and in secret references coming from organization
  configurations ('pass:<path>', 'bitwarden:<item>@<field>') are never interpreted (CVE-2026-123717),
- a missing executable is reported as an inaccessible vault.
"""

import json

import pytest

from otterdog.config import CredentialResolver, OtterdogConfig
from otterdog.credentials import CredentialPlaceHolders
from otterdog.credentials.bitwarden_provider import BitwardenVault
from otterdog.credentials.pass_provider import PassVault

_PASS_OK = {"ls": {"stdout": "Password Store\n"}, "show": {"stdout": "the-secret\n"}}

_BW_ITEM = {
    "login": {"username": "otterdog-bot", "password": "bot-password", "totp": "JBSWY3DPEHPK3PXP"},
    "fields": [
        {"name": "api_token_admin", "value": "ghp_token"},
        {"name": "webhook_secret", "value": "s3cret"},
    ],
}
_BW_OK = {"unlock": {"stdout": "Vault is unlocked!\n"}, "get": {"stdout": json.dumps(_BW_ITEM) + "\n"}}


def _placeholders(org_name: str = "test-org") -> CredentialPlaceHolders:
    return CredentialPlaceHolders(org_name=org_name, github_id=org_name)


def _resolver(tmp_path, provider: str) -> CredentialResolver:
    config = OtterdogConfig(
        {
            "defaults": {
                "jsonnet": {
                    "base_template": "https://github.com/otterdog/test-defaults#test-defaults.libsonnet@main",
                    "config_dir": "orgs",
                },
            },
            "organizations": [{"name": "test-org", "github_id": "test-org", "credentials": {"provider": provider}}],
        },
        False,
        str(tmp_path),
    )
    return CredentialResolver(config)


class TestPass:
    def test_credential_key_is_not_interpreted_by_a_shell(self, fake_cli, injection_payload):
        payload, marker = injection_payload
        cli = fake_cli("pass", _PASS_OK)

        credentials = PassVault().get_credentials(_placeholders(), {"api_token": payload}, only_token=True)

        assert not marker.exists()
        assert credentials.github_token == "the-secret"
        assert cli.invocations[-1] == ["show", payload]

    def test_secret_reference_from_org_config_is_not_interpreted_by_a_shell(
        self, fake_cli, tmp_path, injection_payload
    ):
        # e.g. the secret of a webhook or a repository secret: value: 'pass:bots/<project>/<secret>'
        payload, marker = injection_payload
        cli = fake_cli("pass", _PASS_OK)

        assert _resolver(tmp_path, "pass").get_secret(f"pass:bots/{payload}") == "the-secret"
        assert not marker.exists()
        assert cli.invocations[-1] == ["show", f"bots/{payload}"]

    def test_missing_executable_is_reported_as_inaccessible_vault(self, empty_path):
        with pytest.raises(RuntimeError, match="could not access pass vault:\nfailed to execute 'pass'"):
            PassVault()


class TestBitwarden:
    def test_item_id_is_not_interpreted_by_a_shell(self, fake_cli, injection_payload):
        payload, marker = injection_payload
        cli = fake_cli("bw", _BW_OK)

        credentials = BitwardenVault().get_credentials(_placeholders(), {"item_id": payload}, only_token=True)

        assert not marker.exists()
        assert credentials.github_token == "ghp_token"
        assert cli.invocations == [["unlock", "--check"], ["get", "item", payload]]

    def test_secret_reference_from_org_config_is_not_interpreted_by_a_shell(
        self, fake_cli, tmp_path, injection_payload
    ):
        # e.g. the secret of a webhook or a repository secret: value: 'bitwarden:<item>@<field>'
        payload, marker = injection_payload
        cli = fake_cli("bw", _BW_OK)

        assert _resolver(tmp_path, "bitwarden").get_secret(f"bitwarden:{payload}@webhook_secret") == "s3cret"
        assert not marker.exists()
        assert cli.invocations[-1] == ["get", "item", payload]

    def test_missing_executable_is_reported_as_inaccessible_vault(self, empty_path):
        with pytest.raises(RuntimeError, match="could not access bitwarden vault:\nfailed to execute 'bw'"):
            BitwardenVault()
