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


def _request(navigation=True):
    return pretend.stub(is_navigation_request=lambda: navigation)


def _load_page(client, request, status=None, failed=False):
    """Emits the events of a page load as playwright does."""
    if status is not None:
        client._remember_page_load_status(pretend.stub(status=status, request=request))

    if failed:
        client._record_failed_page_load(request)
    else:
        client._record_page_load(request)


def test_page_loads_are_recorded_once_finished_or_failed():
    client = WebClient(pretend.stub())

    _load_page(client, _request(), 200)
    _load_page(client, _request(), 404)
    # a page load can fail after its response has been received
    _load_page(client, _request(), 200, failed=True)
    _load_page(client, _request(), failed=True)
    # scripts, images and other resources of a page are not of interest
    _load_page(client, _request(navigation=False), 200)
    _load_page(client, _request(navigation=False), failed=True)

    assert client.statistics.total_requests == 4
    assert client.statistics.errors == {"404": 1, "network": 2}
    assert len(client.statistics.quota_cost) == 0
    assert len(client._page_load_statuses) == 0
