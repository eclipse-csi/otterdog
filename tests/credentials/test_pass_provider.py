#  *******************************************************************************
#  Copyright (c) 2023-2025 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from unittest.mock import patch

import pytest

from otterdog.credentials import CredentialPlaceHolders

from . import SHELL_METACHARACTER_VALUES


def _vault(mock_run):
    """Builds a PassVault, swallowing the 'pass ls' probe done in the constructor."""
    from otterdog.credentials.pass_provider import PassVault

    mock_run.return_value = (0, "", "")
    vault = PassVault()
    mock_run.reset_mock()
    return vault


class TestPassProviderArgumentHandling:
    """Configuration supplied keys are handed over as a single, unparsed argument."""

    @pytest.mark.parametrize("value", SHELL_METACHARACTER_VALUES)
    @patch("otterdog.credentials.pass_provider.run_command_sync")
    def test_get_secret_passes_the_key_as_a_single_verbatim_argument(self, mock_run, value):
        vault = _vault(mock_run)
        mock_run.return_value = (0, "the-secret", "")

        assert vault.get_secret(value) == "the-secret"

        # exactly one argv element, byte identical
        mock_run.assert_called_once_with("pass", "show", value)

    @pytest.mark.parametrize("value", SHELL_METACHARACTER_VALUES)
    @patch("otterdog.credentials.pass_provider.run_command_sync")
    def test_get_credentials_passes_the_key_as_a_single_verbatim_argument(self, mock_run, value):
        vault = _vault(mock_run)
        mock_run.return_value = (0, "value", "")

        vault.get_credentials(
            CredentialPlaceHolders(org_name="test-org", github_id="test-org"),
            {"api_token": value, "username": "u", "password": "p", "twofa_seed": "s"},
        )

        assert ("pass", "show", value) in [call.args for call in mock_run.call_args_list]

    @pytest.mark.parametrize("key", ["-c", "--session=evil", "-"])
    @patch("otterdog.credentials.pass_provider.run_command_sync")
    def test_key_starting_with_a_dash_is_rejected(self, mock_run, key):
        vault = _vault(mock_run)

        with pytest.raises(RuntimeError, match="invalid pass key"):
            vault.get_secret(key)

        mock_run.assert_not_called()

    @patch("otterdog.credentials.pass_provider.run_command_sync")
    def test_empty_key_is_rejected(self, mock_run):
        vault = _vault(mock_run)

        with pytest.raises(RuntimeError, match="invalid pass key"):
            vault.get_secret("")

        mock_run.assert_not_called()

    @patch("otterdog.credentials.pass_provider.run_command_sync")
    def test_uses_the_explicit_show_subcommand(self, mock_run):
        # without an explicit 'show', a key named like a sub-command would be executed as one
        vault = _vault(mock_run)
        mock_run.return_value = (0, "s", "")

        vault.get_secret("rm")

        mock_run.assert_called_once_with("pass", "show", "rm")


class TestPassProviderBehaviour:
    @patch("otterdog.credentials.pass_provider.run_command_sync")
    def test_failure_invokes_pass_only_once(self, mock_run):
        vault = _vault(mock_run)
        mock_run.return_value = (1, "", "pass: key not in the password store")

        with pytest.raises(RuntimeError, match="could not be retrieved from your pass vault"):
            vault.get_secret("some/key")

        assert mock_run.call_count == 1

    @patch("otterdog.credentials.pass_provider.run_command_sync")
    def test_failure_reports_stderr(self, mock_run):
        vault = _vault(mock_run)
        mock_run.return_value = (1, "", "gpg: decryption failed")

        with pytest.raises(RuntimeError, match="gpg: decryption failed"):
            vault.get_secret("some/key")

    @patch("otterdog.credentials.pass_provider.run_command_sync")
    def test_non_strict_lookup_returns_empty_string(self, mock_run):
        from otterdog.credentials.pass_provider import PassVault

        _vault(mock_run)
        mock_run.return_value = (1, "", "not found")

        assert PassVault._retrieve_resolved_key("some/key", strict=False) == ""

    @patch("otterdog.credentials.pass_provider.run_command_sync")
    def test_secret_value_is_returned_unmodified(self, mock_run):
        vault = _vault(mock_run)
        mock_run.return_value = (0, "  spaces preserved  ", "")

        assert vault.get_secret("some/key") == "  spaces preserved  "

    @patch("otterdog.credentials.pass_provider.run_command_sync")
    def test_constructor_reports_an_inaccessible_vault(self, mock_run):
        from otterdog.credentials.pass_provider import PassVault

        mock_run.return_value = (1, "", "pass: command not found")

        with pytest.raises(RuntimeError, match="could not access pass vault"):
            PassVault()
