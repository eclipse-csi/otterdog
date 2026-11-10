from contextlib import asynccontextmanager
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


class _MockTotpPage:
    """Mocks a page asking for a TOTP, showing the given title once it has been submitted."""

    def __init__(self, title, title_after_submit, accepts_totp=True):
        self._title = title
        self._title_after_submit = title_after_submit
        self._accepts_totp = accepts_totp
        self._asks_for_totp = True
        self.entered_totps = []

    async def title(self):
        return self._title

    def get_by_role(self, role, name):
        assert (role, name) == ("textbox", "Enter the verification code")
        return pretend.stub(count=self._count_textboxes, fill=self._enter_totp)

    @asynccontextmanager
    async def expect_event(self, event):
        assert event == "load"
        yield

    async def _count_textboxes(self):
        return 1 if self._asks_for_totp else 0

    async def _enter_totp(self, totp):
        self.entered_totps.append(totp)
        self._title = self._title_after_submit
        self._asks_for_totp = not self._accepts_totp


@pytest.mark.asyncio
async def test_2fa_checkup_is_skipped_if_not_requested():
    page = _MockTotpPage("GitHub", "GitHub")
    client = WebClient(pretend.stub(totp="123456"))

    with patch.object(client, "_goto", new=AsyncMock()) as goto:
        await client._perform_2fa_checkup(page)

    goto.assert_not_called()
    assert page.entered_totps == []


@pytest.mark.asyncio
async def test_2fa_checkup_submits_totp():
    page = _MockTotpPage("Verify two-factor authentication", "GitHub")
    client = WebClient(pretend.stub(totp="123456"))

    with (
        patch.object(client, "_goto", new=AsyncMock()) as goto,
        patch.object(client, "_store_html_and_screenshot", new=AsyncMock()),
    ):
        await client._perform_2fa_checkup(page)

    goto.assert_awaited_once_with(page, "https://github.com/settings/two_factor_checkup")
    assert page.entered_totps == ["123456"]


@pytest.mark.asyncio
async def test_2fa_checkup_fails_if_totp_is_not_accepted():
    page = _MockTotpPage("Verify two-factor authentication", "Verify your two-factor configuration", False)
    client = WebClient(pretend.stub(totp="123456"))

    with (
        patch.object(client, "_goto", new=AsyncMock()),
        patch.object(client, "_store_html_and_screenshot", new=AsyncMock()),
        pytest.raises(RuntimeError, match="2FA checkup failed"),
    ):
        await client._perform_2fa_checkup(page)


@pytest.mark.asyncio
@pytest.mark.parametrize("actor", ["octocat", None])
async def test_logged_in_as_returns_actor_of_profile_page(actor):
    async def count():
        return 0 if actor is None else 1

    async def get_attribute(name):
        assert name == "content"
        return actor

    page = pretend.stub(locator=lambda selector: pretend.stub(count=count, get_attribute=get_attribute))
    client = WebClient(pretend.stub())

    with patch.object(client, "_goto", new=AsyncMock()) as goto:
        assert await client._logged_in_as(page) == actor

    goto.assert_awaited_once_with(page, "https://github.com/settings/profile")


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
