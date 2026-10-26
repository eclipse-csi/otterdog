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
    assert client.statistics.retried_requests == 2


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


def _navigation_response(status, navigation=True):
    return pretend.stub(status=status, request=pretend.stub(is_navigation_request=lambda: navigation))


def test_page_loads_are_recorded():
    client = WebClient(pretend.stub())

    client._record_page_load(_navigation_response(200))
    client._record_page_load(_navigation_response(404))
    # scripts, images and other resources of a page are not of interest
    client._record_page_load(_navigation_response(200, navigation=False))
    client._record_failed_page_load(pretend.stub(is_navigation_request=lambda: True))
    client._record_failed_page_load(pretend.stub(is_navigation_request=lambda: False))

    assert client.statistics.total_requests == 3
    assert client.statistics.errors == {"404": 1, "network": 1}
    assert len(client.statistics.quota_cost) == 0
