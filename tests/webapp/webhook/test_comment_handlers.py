#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import re
import unittest
from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from parameterized import parameterized  # type: ignore

from otterdog.webapp.webhook.comment_handlers import (
    ApplyCommentHandler,
    CheckSyncCommentHandler,
    CommentHandler,
    CommentScope,
    DoneCommentHandler,
    HelpCommentHandler,
    MergeCommentHandler,
    TeamInfoCommentHandler,
    ValidateCommentHandler,
)

T = TypeVar("T", bound=CommentHandler)


class CommentHandlerTest(unittest.TestCase, ABC, Generic[T]):
    @property
    @abstractmethod
    def handler(self) -> CommentHandler:
        pass

    def _test_matches(self, test_input, expected):
        match = self.handler.matches(test_input)
        if expected is True:
            assert match is not None
        else:
            assert match is None


class HelpCommentHandlerTest(CommentHandlerTest[HelpCommentHandler]):
    @property
    def handler(self) -> CommentHandler:
        return HelpCommentHandler()

    @parameterized.expand(
        [
            ("/otterdog help", True),
            ("   /otterdog help   ", False),
            ("/help", False),
            ("/otterdog hel", False),
        ]
    )
    def test_matches(self, test_input, expected):
        self._test_matches(test_input, expected)


class TeamInfoCommentHandlerTest(CommentHandlerTest[TeamInfoCommentHandler]):
    @property
    def handler(self) -> TeamInfoCommentHandler:
        return TeamInfoCommentHandler()

    @parameterized.expand(
        [
            ("/otterdog team-info", True),
            ("   /otterdog team-info   ", False),
            ("/team-info", False),
            ("/otterdog team", False),
        ]
    )
    def test_matches(self, test_input, expected):
        self._test_matches(test_input, expected)


class CheckSyncCommentHandlerTest(CommentHandlerTest[CheckSyncCommentHandler]):
    @property
    def handler(self) -> CommentHandler:
        return CheckSyncCommentHandler()

    @parameterized.expand(
        [
            ("/otterdog check-sync", True),
            ("   /otterdog check-sync   ", False),
            ("/check-sync", False),
            ("/otterdog check", False),
        ]
    )
    def test_matches(self, test_input, expected):
        self._test_matches(test_input, expected)


class ApplyCommentHandlerTest(CommentHandlerTest[ApplyCommentHandler]):
    @property
    def handler(self) -> CommentHandler:
        return ApplyCommentHandler()

    @parameterized.expand(
        [
            ("/otterdog apply", True),
            ("   /otterdog apply   ", False),
            ("/apply", False),
            ("/otterdog appl", False),
        ]
    )
    def test_matches(self, test_input, expected):
        self._test_matches(test_input, expected)


class DoneCommentHandlerTest(CommentHandlerTest[DoneCommentHandler]):
    @property
    def handler(self) -> CommentHandler:
        return DoneCommentHandler()

    @parameterized.expand(
        [
            ("/otterdog done", True),
            ("   /otterdog done   ", False),
            ("/done", False),
            ("/otterdog don", False),
        ]
    )
    def test_matches(self, test_input, expected):
        self._test_matches(test_input, expected)


class MergeCommentHandlerTest(CommentHandlerTest[MergeCommentHandler]):
    @property
    def handler(self) -> CommentHandler:
        return MergeCommentHandler()

    @parameterized.expand(
        [
            ("/otterdog merge", True),
            ("   /otterdog merge   ", False),
            ("/merge", False),
            ("/otterdog mer", False),
        ]
    )
    def test_matches(self, test_input, expected):
        self._test_matches(test_input, expected)


class ValidateCommentHandlerTest(CommentHandlerTest[ValidateCommentHandler]):
    @property
    def handler(self) -> CommentHandler:
        return ValidateCommentHandler()

    @parameterized.expand(
        [
            ("/otterdog validate", True),
            ("/otterdog validate info", True),
            ("   /otterdog validate   ", False),
            ("   /otterdog validate   info", False),
            ("/validate", False),
            ("/otterdog validat", False),
        ]
    )
    def test_matches(self, test_input, expected):
        self._test_matches(test_input, expected)


class CommentScopeTest(unittest.TestCase):
    def test_existing_handlers_only_apply_to_config_repo_pull_requests(self):
        for handler in [
            HelpCommentHandler(),
            TeamInfoCommentHandler(),
            CheckSyncCommentHandler(),
            ApplyCommentHandler(),
            DoneCommentHandler(),
            MergeCommentHandler(),
            ValidateCommentHandler(),
        ]:
            assert handler.scope == CommentScope.CONFIG_REPO_PULL_REQUEST
            assert handler.applies_to(is_pull_request=True, is_config_repo=True) is True
            assert handler.applies_to(is_pull_request=True, is_config_repo=False) is False
            assert handler.applies_to(is_pull_request=False, is_config_repo=True) is False
            assert handler.applies_to(is_pull_request=False, is_config_repo=False) is False

    @parameterized.expand(
        [
            (CommentScope.PULL_REQUEST, True, True, True),
            (CommentScope.PULL_REQUEST, True, False, True),
            (CommentScope.PULL_REQUEST, False, True, False),
            (CommentScope.PULL_REQUEST, False, False, False),
            (CommentScope.ANY, True, True, True),
            (CommentScope.ANY, True, False, True),
            (CommentScope.ANY, False, True, True),
            (CommentScope.ANY, False, False, True),
        ]
    )
    def test_scope_matrix(self, scope, is_pull_request, is_config_repo, expected):
        class ScopedHandler(CommentHandler):
            @property
            def scope(self) -> CommentScope:
                return scope_value

            def _create_pattern(self):
                return re.compile(r"/otterdog\s+scoped")

            def process(self, match, event) -> None:
                pass

        scope_value = scope
        assert ScopedHandler().applies_to(is_pull_request, is_config_repo) is expected
