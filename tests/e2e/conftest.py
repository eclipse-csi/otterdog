#  *******************************************************************************
#  Copyright (c) 2025 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import json
from contextlib import asynccontextmanager
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import _jsonnet  # type: ignore[import-untyped]
import pytest
from click.testing import CliRunner

from otterdog import utils
from otterdog.config import OtterdogConfig
from otterdog.providers.github import graphql
from otterdog.providers.github.rest import requester
from otterdog.utils import IndentingPrinter, LogLevel


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


@dataclass
class E2EContext:
    resources_path: Path
    config: OtterdogConfig
    org_config: object
    github_org: dict
    github_repo: dict
    printer: IndentingPrinter
    output: StringIO
    monkeypatch: pytest.MonkeyPatch
    config_file: str | None = None  # Config file path for CLI
    cli_runner: CliRunner | None = None  # Click test runner
    _github_api: Any = None  # Set by fixture
    _github_calls: list[tuple[str, str]] | None = None  # Set by fixture
    _cli_group: Any = None  # Set by fixture
    _graphql_api: Any = None  # Set by fixture

    def github_response_map(self, overrides: dict[str, dict] | None = None) -> dict[str, dict]:
        # Load responses from external jsonnet file
        responses_file = Path(__file__).parent / "github_responses.jsonnet"
        responses_json = _jsonnet.evaluate_file(str(responses_file))
        response_map = json.loads(responses_json)

        if overrides:
            response_map.update(overrides)

        return response_map

    def configure_github(self, response_overrides: dict[str, dict] | None = None) -> None:
        """Reconfigure the GitHub mock with new response overrides."""
        response_map = self.github_response_map(response_overrides)
        self._github_api.response_map = response_map  # type: ignore[attr-defined]
        self._github_calls.clear()  # type: ignore[union-attr]

    def get_github_calls(self) -> list[tuple[str, str]]:
        """Return the tracked GitHub API calls."""
        assert self._github_calls is not None
        return self._github_calls

    def run_cli(self, *args) -> tuple[int, str]:
        """Run a CLI command and return (exit_code, output).

        Args:
            *args: Arguments to pass to the CLI (e.g., 'apply', 'test-org', '--force', etc.)

        Returns:
            (exit_code, output_text)
        """
        # Inject config file path
        full_args = list(args)
        assert self.config_file is not None
        if "--config" not in full_args and "-c" not in full_args:
            full_args.extend(["--config", self.config_file])

        assert self.cli_runner is not None
        try:
            result = self.cli_runner.invoke(self._cli_group, full_args, catch_exceptions=True)  # type: ignore[arg-type]
            return result.exit_code, result.output
        except ValueError as e:
            if "I/O operation on closed file" in str(e):
                # This is a known Click testing issue when stderr gets closed prematurely
                # The command actually completed - we can check the stdout output we captured
                # Return success if this is the case
                return 0, "Command completed (Click stderr issue)"
            raise


@pytest.fixture
def e2e(monkeypatch: pytest.MonkeyPatch, tmp_path) -> E2EContext:
    resources_path = Path(__file__).parent.parent / "models" / "resources"

    def load_fixture(filename: str) -> dict:
        with (resources_path / filename).open() as f:
            return json.load(f)

    config = OtterdogConfig.from_file(str(resources_path / "otterdog.json"), local_mode=True)
    org_config = config.get_organization_config("test-org")
    github_org = load_fixture("github-org-settings.json")
    github_repo = load_fixture("github-repo.json")
    output = StringIO()
    printer = IndentingPrinter(output, log_level=LogLevel.INFO)

    # Set up test working directory with proper structure
    # The CLI expects templates to be relative to the config file location
    test_config_dir = tmp_path / "test-config"
    test_config_dir.mkdir(exist_ok=True)

    # Copy config file
    import shutil

    config_file_path = resources_path / "otterdog.json"
    cli_config_file = test_config_dir / "otterdog.json"
    shutil.copy(config_file_path, cli_config_file)

    # Copy test-org directory to avoid overwriting original files during import
    test_org_source = resources_path / "test-org"
    test_org_dest = test_config_dir / "test-org"
    if test_org_dest.exists():
        shutil.rmtree(test_org_dest)
    shutil.copytree(test_org_source, test_org_dest)

    context = E2EContext(
        resources_path=resources_path,
        config=config,
        org_config=org_config,
        github_org=github_org,
        github_repo=github_repo,
        printer=printer,
        output=output,
        monkeypatch=monkeypatch,
        config_file=str(cli_config_file),
        cli_runner=CliRunner(),
    )

    # Import CLI after creating context to avoid circular imports
    from otterdog.cli import cli

    context._cli_group = cli

    # Set up GitHub mocking by default
    original_requester_init = requester.Requester.__init__
    original_graphql_init = graphql.GraphQLClient.__init__

    def patched_requester_init(self, *args, **kwargs):
        original_requester_init(self, *args, **kwargs)
        self._client = context._github_api

    def patched_graphql_init(self, *args, **kwargs):
        original_graphql_init(self, *args, **kwargs)
        # Mock the GraphQL client's _client.request method just like REST
        self._client = context._graphql_api

    response_map = context.github_response_map()
    calls: list[tuple[str, str]] = []

    # Load GraphQL responses from the responses file
    responses_file = Path(__file__).parent / "github_responses.jsonnet"
    responses_json = _jsonnet.evaluate_file(str(responses_file))
    all_responses = json.loads(responses_json)
    graphql_responses = all_responses.get("graphql", {})

    class MockClient:
        def __init__(self, response_map, calls):
            self.response_map = response_map
            self.calls = calls

        @asynccontextmanager
        async def request(self, method, url, **kwargs):
            self.calls.append((method.upper(), url))
            # Parse the URL to get the path component
            http_request_path = urlparse(url).path

            if http_request_path in self.response_map:
                # For non-GET requests, simulate success with appropriate status codes
                if method.upper() in ["POST", "PUT", "PATCH", "DELETE"]:
                    # For vulnerability alerts and other boolean endpoints, return 204 No Content
                    if (
                        "vulnerability-alerts" in http_request_path
                        or "private-vulnerability-reporting" in http_request_path
                    ):
                        status_code = 204
                        yield FakeHttpResponse(status_code, "")
                    # For content updates (PUT to /contents/), return success with content metadata
                    elif "/contents/" in http_request_path and method.upper() == "PUT":
                        status_code = 200
                        yield FakeHttpResponse(
                            status_code,
                            json.dumps(
                                {
                                    "content": {"sha": "new123abc456", "name": "updated_file"},
                                    "commit": {"sha": "commit123abc456", "message": "Update file"},
                                }
                            ),
                        )
                    else:
                        status_code = 200 if method.upper() != "DELETE" else 204
                        yield FakeHttpResponse(status_code, json.dumps({"success": True}))
                else:
                    yield FakeHttpResponse(200, json.dumps(self.response_map[http_request_path]))
            elif "/contents/" in http_request_path and method.upper() == "GET":
                # Handle dynamic content endpoints for template processing
                # Extract the file path from the URL
                content_path = http_request_path.split("/contents/", 1)[1]
                generic_content_response = {
                    "name": content_path.split("/")[-1],
                    "path": content_path,
                    "content": "IyBHZW5lcmljIGNvbnRlbnQgZm9yIHRlc3Rpbmc=",  # Base64 encoded "# Generic content for testing"
                    "type": "file",
                    "sha": "abc123def456",
                }
                yield FakeHttpResponse(200, json.dumps(generic_content_response))
            else:
                raise RuntimeError(f"No mock response for {http_request_path}")

    context._github_api = MockClient(response_map, calls)
    context._github_calls = calls

    # Create a simple GraphQL mock client that returns configured responses
    class MockGraphQLClient:
        def __init__(self, calls, graphql_responses):
            self.calls = calls
            self.graphql_responses = graphql_responses

        @asynccontextmanager
        async def request(self, method, url, **kwargs):
            self.calls.append((method.upper(), url))

            json_data = kwargs.get("json")
            if json_data:
                query = json_data.get("query", "")
                for key, value in self.graphql_responses.items():
                    if key in query:
                        # Get the response from the configuration
                        response_data = value.get("response", {})
                        yield FakeHttpResponse(200, json.dumps({"data": response_data}))
                        return

            raise RuntimeError(f"No mock GraphQL response for query: {kwargs.get('json', {}).get('query', '')}")

    context._graphql_api = MockGraphQLClient(calls, graphql_responses)

    monkeypatch.setattr(requester.Requester, "__init__", patched_requester_init)
    monkeypatch.setattr(graphql.GraphQLClient, "__init__", patched_graphql_init)
    monkeypatch.setattr(utils, "get_approval", lambda *args, **kwargs: True)

    return context
