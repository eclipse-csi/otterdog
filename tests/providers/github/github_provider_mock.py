"""
Allows tests to define expected HTTP interactions and verify that the GitHubProvider
uses the GitHub API as intended.

This mock allows specifying expected HTTP requests together with their responses,
and verifies that all expected requests were actually made. It is intentionally
strict and is designed to validate correct API usage.

Most of the code is dedicated to detailed and actionable error reporting when an
unexpected request is made, as a simple "unexpected call" error is usually not
sufficient to understand what went wrong.

Alternatives considered: aioresponses and pytest-aiohttp. While both are useful
libraries, they do not match the required contract-testing use case closely enough.
Adapting them to provide the same level of request validation and diagnostics would
require even more code and add additional complexity.
"""

import json as jsonlib
from collections.abc import Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import pytest
import pytest_asyncio

import otterdog.providers.github.rest as github_rest
from otterdog.credentials import Credentials
from otterdog.providers.github import GitHubProvider

if TYPE_CHECKING:
    from aiohttp_retry import RetryClient


def _pretty_json(obj: Mapping[str, object] | None) -> str | None:
    """Stable, pretty JSON encoding for comparisons and diagnostics."""
    return jsonlib.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False) if obj is not None else None


class FakeHttpResponse:
    """Fake aiohttp response object that the Requester expects."""

    def __init__(self, status: int, text: str, headers: dict | None = None):
        if not headers:
            headers = {}
        if "x-ratelimit-remaining" not in headers:
            headers["x-ratelimit-remaining"] = "5000"

        self.status = status
        self.headers = headers
        self.links = None
        self.from_cache = False

        self._text = text

    async def text(self):
        return self._text


@dataclass(frozen=True)
class HttpRequest:
    """Used for expected and actual HTTP requests."""

    method: str
    url: str
    # Encoded as str for easier comparison and hashing
    params_str: str | None
    json_str: str | None


class HttpClientMock:
    """
    Mocks aiohttp_retry.RetryClient, which is used internally by the GitHubProvider.
    The method of interest is 'request', which is an async context manager.
    """

    def __init__(self) -> None:
        self.expected: dict[HttpRequest, FakeHttpResponse] = {}
        self.served_requests: list[HttpRequest] = []

    def _format_unexpected_request_details(self, actual_request: HttpRequest, debug_info) -> str:
        for expected_request in self.expected:
            if actual_request.method == expected_request.method and actual_request.url == expected_request.url:
                msg = (
                    f"Found matching method and URL for {actual_request.method} {actual_request.url}, "
                    f"but request details did not match exactly.\n"
                )

                if expected_request.params_str != actual_request.params_str:
                    msg += "\nExpected params:\n"
                    msg += f"{expected_request.params_str or '∅'}\n"
                    msg += "Actual params:\n"
                    msg += f"{actual_request.params_str or '∅'}\n"

                if expected_request.json_str != actual_request.json_str:
                    msg += "\nExpected JSON:\n"
                    msg += f"{expected_request.json_str or '∅'}\n"
                    msg += "Actual JSON:\n"
                    msg += f"{actual_request.json_str or '∅'}\n"

                if debug_info:
                    msg += "\nOther request details (actual):\n"
                    for key, value in debug_info.items():
                        msg += f"  {key}: {value}\n"

                return msg

        msg = f"No matching response found for {actual_request.method} {actual_request.url}.\n"
        if self.expected:
            msg += "\nAvailable expected requests:\n"
            msg += "\n".join(f"{r.method} {r.url}" for r in self.expected)
        if self.served_requests:
            msg += "\nServed requests so far:\n"
            msg += "\n".join(f"{r.method} {r.url}" for r in self.served_requests)

        return msg

    def _retrieve_matching_response(self, actual_request: HttpRequest, debug_info) -> FakeHttpResponse:
        if actual_request in self.expected:
            return self.expected.pop(actual_request)
        else:
            msg = self._format_unexpected_request_details(actual_request, debug_info)
            pytest.fail(msg, pytrace=False)

    def verify_all_called(self) -> None:
        if warnings := [f"Expected request not made: {exp.method} {exp.url}" for exp in self.expected]:
            pytest.fail("\n".join(warnings), pytrace=False)

    @staticmethod
    def _normalize_json_and_data(
        json: dict[str, str | int | bool] | None,
        data: str | None,
    ) -> str | None:
        # Mirror aiohttp semantics: json and data must not both be set.
        if json is not None and data is not None:
            raise ValueError("Otterdog has specified both json and data in the same request")

        # If data is present, interpret it as JSON (Otterdog uses JSON APIs for GitHub).
        if data is not None:
            if data == "":
                raise ValueError("Otterdog has specified an empty string as data in the request body")

            try:
                json = jsonlib.loads(data)
            except Exception:
                raise ValueError(f"Otterdog has specified non-JSON data in the request body: {data!r}") from None

        # Enforce invariant: empty JSON bodies are not allowed
        if json == {}:
            raise ValueError("Otterdog has specified an empty JSON object as the request body")

        # Store as stable pretty JSON string
        return _pretty_json(json)

    @asynccontextmanager
    async def request(
        self,
        method: str,
        url: str,
        json: dict[str, str | int | bool] | None = None,
        data: str | None = None,
        params: dict[str, str | int | bool] | None = None,
        **kwargs,
    ):
        """
        This is called by GitHubProvider (through one of its clients) to make requests.
        It's an async context manager that yields a FakeHttpResponse.
        """

        actual_request = HttpRequest(
            method=method.upper(),
            url=urlparse(url).path,
            params_str=_pretty_json(params),
            json_str=HttpClientMock._normalize_json_and_data(json, data),
        )

        self.served_requests.append(actual_request)
        yield self._retrieve_matching_response(actual_request, kwargs)

    def expect(
        self,
        method: str,
        url: str,
        *,
        response_status: int = 200,
        response_text: str = "",
        request_json: dict[str, object] | None = None,
        request_params: dict[str, str | int | bool] | None = None,
        response_json: dict[str, object] | None = None,
    ) -> None:
        expected = HttpRequest(
            method=method.upper(),
            url=url,
            params_str=_pretty_json(request_params),
            json_str=_pretty_json(request_json),
        )

        if response_json is not None:
            if response_text:
                raise ValueError("Cannot specify both response_text and response_json")
            response_text = jsonlib.dumps(response_json, ensure_ascii=False)

        self.expected[expected] = FakeHttpResponse(status=response_status, text=response_text)


class GitHubProviderTestKit:
    """
    Combines HttpClientMock and a preconfigured GitHubProvider for easier use in tests.
    Also provides small domain helpers for common GitHub API patterns (e.g. secrets encryption).
    """

    def __init__(self, monkeypatch: pytest.MonkeyPatch):
        self._monkeypatch = monkeypatch

        self.client = HttpClientMock()
        credentials = Credentials(
            "fake-user", "fake-password", "fake-totp-secret", "fake-github-token", "fake-last-totp"
        )
        http_client: RetryClient = self.client  # type: ignore
        self.provider = GitHubProvider(credentials, http_client)

    def expect(
        self,
        method: str,
        url: str,
        *,
        request_json: dict[str, object] | None = None,
        request_params: dict[str, str | int | bool] | None = None,
        response_json: dict[str, object] | None = None,
        response_status: int = 200,
        response_text: str = "",
    ) -> None:
        self.client.expect(
            method=method,
            url=url,
            request_json=request_json,
            request_params=request_params,
            response_json=response_json,
            response_status=response_status,
            response_text=response_text,
        )

    def fake_encryption(self, params: tuple[str, str], ciphertext: str) -> None:
        """
        Make encryption deterministic in tests.

        Encrypting the same value with the same public key produces different ciphertexts
        due to randomization. To keep tests deterministic, patch github_rest.encrypt_value
        to return a constant ciphertext for the given (public_key, plaintext) input.

        Usage:
            github_mock.fake_encryption((public_key, plaintext), ciphertext)
        """

        def encrypt_value(pk: str, value: str) -> str:
            assert pk == params[0], f"unexpected public key: {pk!r}"
            assert value == params[1], f"unexpected secret value: {value!r}"
            return ciphertext

        self._monkeypatch.setattr(github_rest, "encrypt_value", encrypt_value)


# Last, but not least, this is the fixture that tests will use.
@pytest_asyncio.fixture
async def github(monkeypatch: pytest.MonkeyPatch):
    """Fixture that provides a GitHubProviderTestKit instance for testing, verifying no warnings after use."""
    mock = GitHubProviderTestKit(monkeypatch)
    try:
        yield mock
        mock.client.verify_all_called()
    finally:
        await mock.provider.close()
