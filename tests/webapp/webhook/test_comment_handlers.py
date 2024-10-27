#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import unittest
from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from parameterized import parameterized  # type: ignore

from otterdog.webapp.webhook.comment_handlers import (
    ApplyCommentHandler,
    CheckSyncCommentHandler,
    CommentHandler,
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
