#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import pytest
import pytest_asyncio

from otterdog.credentials import Credentials
from otterdog.providers.github import GitHubProvider

from .helpers.http_mock import HttpClientMock


class GitHubProviderTestKit:
    """
    Combines HttpClientMock and a preconfigured GitHubProvider for easier use in tests.
    Also provides small domain helpers for common GitHub API patterns (e.g. secrets encryption).
    """

    def __init__(self, monkeypatch: pytest.MonkeyPatch):
        self._monkeypatch = monkeypatch

        self.http = HttpClientMock()
        self.provider = self._create_provider_with_mock_client()

    def _create_provider_with_mock_client(self) -> GitHubProvider:
        import otterdog.providers.github.rest.requester as requester

        credentials = Credentials(
            "fake-user",
            "fake-password",
            "fake-totp-secret",
            "fake-github-token",
            "fake-last-totp",
        )

        self._monkeypatch.setattr(requester, "RetryClient", lambda *args, **kwargs: self.http)
        return GitHubProvider(credentials)

    def fake_encryption(self, params: tuple[str, str], ciphertext: str) -> None:
        """
        Make encryption deterministic in tests.

        Encrypting the same value with the same public key produces different ciphertexts
        due to randomization. To keep tests deterministic, patch github_rest.encrypt_value
        to return a constant ciphertext for the given (public_key, plaintext) input.

        Usage:
            github_mock.fake_encryption((public_key, plaintext), ciphertext)
        """

        # we need to patch the encrypt_value function where it is being used
        # see: https://docs.python.org/3/library/unittest.mock.html#where-to-patch
        import otterdog.providers.github.rest.org_client as org_client
        import otterdog.providers.github.rest.repo_client as repo_client

        def encrypt_value(pk: str, value: str) -> str:
            assert pk == params[0], f"unexpected public key: {pk!r}"
            assert value == params[1], f"unexpected secret value: {value!r}"
            return ciphertext

        self._monkeypatch.setattr(org_client, "encrypt_value", encrypt_value)
        self._monkeypatch.setattr(repo_client, "encrypt_value", encrypt_value)


# Last, but not least, this is the fixture that tests will use.
@pytest_asyncio.fixture
async def github(monkeypatch: pytest.MonkeyPatch):
    """Fixture that provides a GitHubProviderTestKit instance for testing, verifying no warnings after use."""
    mock = GitHubProviderTestKit(monkeypatch)
    try:
        yield mock
        mock.http.verify_all_called()
    finally:
        await mock.provider.close()
