#  *******************************************************************************
#  Copyright (c) 2023-2025 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import logging
from unittest.mock import AsyncMock

from otterdog.credentials import Credentials
from otterdog.providers.github.web import WebClient


class TestWebClient:
    async def test_retrieve_settings_skips_dependent_when_parent_retrieval_fails(self, caplog):
        caplog.set_level(logging.WARNING)

        client = WebClient(Credentials("user", "pwd", "totp", "token"))
        client._goto = AsyncMock()
        client._store_html_and_screenshot = AsyncMock()

        page = AsyncMock()
        page.eval_on_selector = AsyncMock(side_effect=Exception("selector not found"))

        page_def = [
            {
                "name": "has_discussions",
                "optional": False,
                "type": "checkbox",
                "selector": 'input[type="checkbox"][name="discussions_enabled"]',
                "preSelector": None,
                "valueSelector": "checked",
            },
            {
                "name": "discussion_source_repository",
                "optional": False,
                "parent": "has_discussions",
            },
        ]

        settings = await client._retrieve_settings(
            "eclipse-cfm",
            "settings/discussions",
            page_def,
            {"has_discussions", "discussion_source_repository"},
            page,
        )

        assert settings == {}
        client._store_html_and_screenshot.assert_awaited_once()
        assert any(
            "failed to retrieve parent setting 'has_discussions', skipping dependent setting 'discussion_source_repository'"
            in record.message
            for record in caplog.records
        )

    async def test_retrieve_settings_sets_dependent_to_none_when_parent_not_requested(self):
        client = WebClient(Credentials("user", "pwd", "totp", "token"))
        client._goto = AsyncMock()
        client._store_html_and_screenshot = AsyncMock()

        page = AsyncMock()
        page.eval_on_selector = AsyncMock()

        page_def = [
            {
                "name": "discussion_source_repository",
                "optional": False,
                "parent": "has_discussions",
            },
        ]

        settings = await client._retrieve_settings(
            "eclipse-cfm",
            "settings/discussions",
            page_def,
            {"discussion_source_repository"},
            page,
        )

        assert settings == {"discussion_source_repository": None}
        page.eval_on_selector.assert_not_called()
