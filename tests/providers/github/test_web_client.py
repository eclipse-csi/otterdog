from unittest.mock import AsyncMock, patch

import pretend
import pytest

from otterdog.providers.github.web import WebClient


class _MockPage:
    def __init__(self, responses):
        self._responses = responses
        self.goto_calls = []

    async def goto(self, url):
        self.goto_calls.append(url)
        return self._responses[len(self.goto_calls) - 1]

    async def title(self):
        return "Mock Title"

    async def content(self):
        return "<html></html>"


@pytest.mark.asyncio
async def test_goto_retries_repository_defaults_page_on_404():
    page = _MockPage(
        [
            pretend.stub(ok=False, status=404),
            pretend.stub(ok=False, status=404),
            pretend.stub(ok=True, status=200),
        ]
    )
    client = WebClient(pretend.stub())

    with (
        patch("otterdog.providers.github.web.sleep", new=AsyncMock()),
        patch.object(client, "_store_html_and_screenshot", new=AsyncMock()),
    ):
        await client._goto(page, "https://github.com/organizations/example/settings/repository-defaults")

    assert len(page.goto_calls) == 3


@pytest.mark.asyncio
async def test_goto_does_not_retry_non_repository_defaults_page_on_404():
    page = _MockPage(
        [
            pretend.stub(ok=False, status=404),
        ]
    )
    client = WebClient(pretend.stub())

    with (
        patch("otterdog.providers.github.web.sleep", new=AsyncMock()),
        patch.object(client, "_store_html_and_screenshot", new=AsyncMock()),
        pytest.raises(RuntimeError, match="unable to load github page"),
    ):
        await client._goto(page, "https://github.com/organizations/example/settings/security")

    assert len(page.goto_calls) == 1
