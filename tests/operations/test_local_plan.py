#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from io import StringIO
from unittest.mock import AsyncMock

from pretend import stub

from otterdog.operations.local_plan import LocalPlanOperation
from otterdog.utils import IndentingPrinter, LogLevel


def _operation() -> tuple[LocalPlanOperation, StringIO]:
    operation = LocalPlanOperation("-BASE", "*", False, False, False, "")
    output = StringIO()
    operation.init(None, IndentingPrinter(output, log_level=LogLevel.WARN))  # type: ignore
    operation._gh_client = object()  # type: ignore
    return operation, output


async def test_existing_repositories_are_reported():
    operation, output = _operation()
    current_org = stub(add_existing_repositories_from_provider=AsyncMock(return_value=["repo-b", "repo-a"]))

    await operation.add_existing_repositories(current_org, object(), object())  # type: ignore

    current_org.add_existing_repositories_from_provider.assert_awaited_once()
    assert current_org.add_existing_repositories_from_provider.await_args.args[3] == "*"
    text = output.getvalue()
    assert "already exist on GitHub" in text
    assert text.index("- repo-a") < text.index("- repo-b")


async def test_nothing_reported_without_existing_repositories():
    operation, output = _operation()
    current_org = stub(add_existing_repositories_from_provider=AsyncMock(return_value=[]))

    await operation.add_existing_repositories(current_org, object(), object())  # type: ignore

    assert "already exist on GitHub" not in output.getvalue()


async def test_nothing_done_without_expected_organization():
    operation, _ = _operation()
    current_org = stub(add_existing_repositories_from_provider=AsyncMock())

    await operation.add_existing_repositories(current_org, None, object())  # type: ignore

    current_org.add_existing_repositories_from_provider.assert_not_awaited()
