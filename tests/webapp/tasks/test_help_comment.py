#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import pytest
from quart import render_template

# some organizations have dozens of approval teams
_MANY_TEAMS = "team " + " or ".join(f"'project-{i}-leads'" for i in range(60))


async def _render(app, template: str, **context) -> str:
    async with app.app_context():
        return await render_template(template, **context)


async def test_help_comment_lists_the_conditions_of_the_auto_merge(app):
    comment = await _render(
        app,
        "comment/help_comment.txt",
        team_description="team 'project-leads'",
        admin_teams=["org/admins"],
    )

    assert "If you are neither a member of an approval team nor of an admin team, ask one of their members" in comment
    assert "written or approved by a member of an approval team or of an admin team" in comment
    assert "the changes add or change no secret (webhook secrets included)" in comment
    assert "incur no cost" in comment
    assert "only the configuration of the organization is modified" in comment
    assert "- **Approval teams**: team 'project-leads'\n" in comment
    assert "- **Admin teams**: `org/admins`\n" in comment
    assert "(only accessible for the author and for members of an approval team or of an admin team)" in comment


@pytest.mark.parametrize(
    "team_description",
    [
        _MANY_TEAMS,
        "no approval teams are configured (GITHUB_APPROVAL_TEAMS is empty)",
        "a team matching pattern 'project-leads$' (no team in this organization currently matches any of these patterns)",
    ],
    ids=["many_teams", "no_team_configured", "no_team_matching"],
)
async def test_help_comment_shows_the_approval_teams_once_in_a_collapsed_section(app, team_description):
    comment = await _render(
        app,
        "comment/help_comment.txt",
        team_description=team_description,
        admin_teams=["org/admins"],
    )

    assert comment.count(team_description) == 1
    assert f"- **Approval teams**: {team_description}\n" in comment
    teams_section = comment.index("<summary>Approval and admin teams</summary>")
    assert teams_section < comment.index(team_description) < comment.index("</details>", teams_section)


async def test_help_and_auto_merge_comments_list_the_same_conditions(app):
    help_comment = await _render(
        app,
        "comment/help_comment.txt",
        team_description="team 'project-leads'",
        admin_teams=["org/admins"],
    )
    auto_merge_comment = await _render(
        app,
        "comment/auto_merge_comment.txt",
        team_description="team 'project-leads'",
    )

    for condition in (
        "- the pull request is written or approved by a member of an approval team or of an admin team\n",
        (
            "- the changes add or change no secret (webhook secrets included), change no setting of the Web UI, "
            "incur no cost and remove no resource\n"
        ),
        "- only the configuration of the organization is modified\n",
    ):
        assert condition in help_comment
        assert condition in auto_merge_comment
