#  *******************************************************************************
#  Copyright (c) 2023-2025 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import json
from unittest.mock import patch

import pytest

from otterdog.credentials import CredentialPlaceHolders

from . import SHELL_METACHARACTER_VALUES

ITEM = {
    "object": "item",
    "id": "118276ad-158c-4720-b68d-af8c00fe3481",
    "name": "an item",
    "fields": [
        {"name": "api_token_admin", "value": "the-token"},
        {"name": "secret", "value": "the-secret"},
        {"name": "we@ird", "value": "weird-value"},
    ],
    "login": {"username": "user", "password": "pass", "totp": "seed"},
}


def _vault(mock_run):
    """Builds a BitwardenVault, swallowing the 'bw unlock --check' probe done in the constructor."""
    from otterdog.credentials.bitwarden_provider import BitwardenVault

    mock_run.return_value = (0, "", "")
    vault = BitwardenVault()
    mock_run.reset_mock()
    return vault


class TestBitwardenProviderArgumentHandling:
    """Configuration supplied item ids are handed over as a single, unparsed argument."""

    @pytest.mark.parametrize("value", SHELL_METACHARACTER_VALUES)
    @patch("otterdog.credentials.bitwarden_provider.run_command_sync")
    def test_get_secret_passes_the_item_id_as_a_single_verbatim_argument(self, mock_run, value):
        vault = _vault(mock_run)
        mock_run.return_value = (0, json.dumps(ITEM), "")

        assert vault.get_secret(f"{value}@secret") == "the-secret"

        # exactly one argv element, byte identical
        mock_run.assert_called_once_with("bw", "get", "item", value)

    @pytest.mark.parametrize("value", SHELL_METACHARACTER_VALUES)
    @patch("otterdog.credentials.bitwarden_provider.run_command_sync")
    def test_get_credentials_passes_the_item_id_as_a_single_verbatim_argument(self, mock_run, value):
        vault = _vault(mock_run)
        mock_run.return_value = (0, json.dumps(ITEM), "")

        vault.get_credentials(
            CredentialPlaceHolders(org_name="test-org", github_id="test-org"),
            {"item_id": value},
        )

        mock_run.assert_called_once_with("bw", "get", "item", value)

    @pytest.mark.parametrize("item_id", ["-c", "--session=evil", "-"])
    @patch("otterdog.credentials.bitwarden_provider.run_command_sync")
    def test_item_id_starting_with_a_dash_is_rejected(self, mock_run, item_id):
        vault = _vault(mock_run)

        with pytest.raises(RuntimeError, match="invalid bitwarden item id"):
            vault.get_secret(f"{item_id}@secret")

        mock_run.assert_not_called()

    @patch("otterdog.credentials.bitwarden_provider.run_command_sync")
    def test_empty_item_id_is_rejected(self, mock_run):
        vault = _vault(mock_run)

        with pytest.raises(RuntimeError, match="invalid bitwarden item id"):
            vault.get_secret("@secret")

        mock_run.assert_not_called()


class TestBitwardenProviderBehaviour:
    @patch("otterdog.credentials.bitwarden_provider.run_command_sync")
    def test_get_credentials_returns_all_fields(self, mock_run):
        vault = _vault(mock_run)
        mock_run.return_value = (0, json.dumps(ITEM), "")

        credentials = vault.get_credentials(
            CredentialPlaceHolders(org_name="test-org", github_id="test-org"),
            {"item_id": ITEM["id"]},
        )

        assert credentials.github_token == "the-token"
        assert credentials.username == "user"
        assert credentials.password == "pass"

    @patch("otterdog.credentials.bitwarden_provider.run_command_sync")
    def test_secret_key_may_contain_an_at_sign(self, mock_run):
        # the item id is separated on the first '@' only
        vault = _vault(mock_run)
        mock_run.return_value = (0, json.dumps(ITEM), "")

        assert vault.get_secret(f"{ITEM['id']}@we@ird") == "weird-value"

        mock_run.assert_called_once_with("bw", "get", "item", ITEM["id"])

    @patch("otterdog.credentials.bitwarden_provider.run_command_sync")
    def test_secret_data_without_a_separator_is_rejected(self, mock_run):
        vault = _vault(mock_run)

        with pytest.raises(RuntimeError, match="failed to parse secret data"):
            vault.get_secret("no-separator-here")

    @patch("otterdog.credentials.bitwarden_provider.run_command_sync")
    def test_surrounding_output_is_trimmed_on_both_paths(self, mock_run):
        # the cli may emit a banner around the json object, both lookups must cope with it
        vault = _vault(mock_run)
        mock_run.return_value = (0, f"a warning\n{json.dumps(ITEM)}\ntrailing noise", "")

        assert vault.get_secret(f"{ITEM['id']}@secret") == "the-secret"

        credentials = vault.get_credentials(
            CredentialPlaceHolders(org_name="test-org", github_id="test-org"),
            {"item_id": ITEM["id"]},
            only_token=True,
        )
        assert credentials.github_token == "the-token"

    @patch("otterdog.credentials.bitwarden_provider.run_command_sync")
    def test_unparseable_output_raises_a_clean_error(self, mock_run):
        vault = _vault(mock_run)
        mock_run.return_value = (0, "not json at all", "")

        with pytest.raises(RuntimeError, match="unexpected output while reading item"):
            vault.get_secret(f"{ITEM['id']}@secret")

    @patch("otterdog.credentials.bitwarden_provider.run_command_sync")
    def test_missing_item_reports_stderr(self, mock_run):
        vault = _vault(mock_run)
        mock_run.return_value = (1, "", "Not found.")

        with pytest.raises(RuntimeError, match=r"Not found\."):
            vault.get_secret(f"{ITEM['id']}@secret")

    @patch("otterdog.credentials.bitwarden_provider.run_command_sync")
    def test_constructor_reports_a_locked_vault(self, mock_run):
        from otterdog.credentials.bitwarden_provider import BitwardenVault

        mock_run.return_value = (1, "", "You are not logged in.")

        with pytest.raises(RuntimeError, match="could not access bitwarden vault"):
            BitwardenVault()
