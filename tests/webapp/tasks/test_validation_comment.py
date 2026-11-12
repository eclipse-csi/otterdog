#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from quart import render_template

from otterdog.webapp.tasks.validate_pull_request import ValidationResult


def test_validation_result_without_blockers_supports_auto_merge():
    result = ValidationResult(
        validation_success=True,
        requires_secrets=False,
        requires_web_ui=False,
        cost_related=False,
        includes_deletions=False,
    )

    assert result.auto_merge_blockers() == []
    assert result.supports_auto_merge is True


def test_validation_result_lists_every_auto_merge_blocker():
    result = ValidationResult(
        touches_non_configuration=True,
        requires_secrets=True,
        requires_web_ui=True,
        cost_related=True,
        includes_deletions=True,
    )

    assert result.auto_merge_blockers() == [
        "some of the requested changes require secrets",
        "some of the requested changes require accessing the Web UI",
        "some of the requested changes may incur costs",
        "some of the requested changes remove resources",
        "the pull request modifies files other than the organization configuration",
    ]
    assert result.supports_auto_merge is False


async def _render(app, **kwargs) -> str:
    async with app.app_context():
        return await render_template(
            "comment/validation_comment.txt",
            sha="head-sha",
            result="Plan: 0 to add, 0 to change, 1 to delete.",
            admin_teams=["test-org/admins"],
            **kwargs,
        )


async def test_validation_comment_explains_why_auto_merge_is_not_available(app):
    comment = await _render(
        app,
        warnings=[],
        auto_merge_blockers=[
            "some of the requested changes remove resources",
            "the pull request modifies files other than the organization configuration",
        ],
    )

    # the list must stay inside the quote block, an empty line would end it
    assert (
        "> [!NOTE]\n"
        "> This pull request cannot be auto-merged via `/otterdog merge`:\n"
        ">\n"
        "> - some of the requested changes remove resources\n"
        "> - the pull request modifies files other than the organization configuration\n"
        ">\n"
        "> It needs to be reviewed and merged by a member of the admin team(s).\n"
    ) in comment
    # the admin teams are the only ones who can move the pull request forward
    assert "cc @test-org/admins" in comment
    assert "### Warnings" not in comment


async def test_validation_comment_without_blockers_does_not_mention_auto_merge(app):
    comment = await _render(app, warnings=[], auto_merge_blockers=[])

    assert "/otterdog merge" not in comment
    assert "cc @" not in comment
