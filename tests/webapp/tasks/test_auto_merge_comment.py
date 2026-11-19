#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from pathlib import Path

from quart import render_template

# some organizations have dozens of approval teams
_MANY_TEAMS = "team " + " or ".join(f"'project-{i}-leads'" for i in range(60))


async def _render(app, team_description: str) -> str:
    async with app.app_context():
        return await render_template("comment/auto_merge_comment.txt", team_description=team_description)


async def test_auto_merge_comment_tells_who_can_merge_and_how(app):
    comment = await _render(app, "team 'project-leads'")

    # the header is used to find out whether the comment has already been posted
    assert comment.startswith("<!-- Otterdog Comment: automerge -->\n")

    # the command comes first, in a code block that can be copied
    assert "```\n/otterdog merge\n```" in comment
    assert comment.index("/otterdog merge") < comment.index("<details>")

    assert (
        "The author of the pull request, or a member of an approval team or of an admin team, can run this command."
        in comment
    )
    assert "the changes add or change no secret (webhook secrets included)" in comment

    link = f"({app.config['DOCUMENTATION_URL']}userguide/workflow/#can-my-pull-request-be-auto-merged)"
    assert link in comment

    # the section of the documentation listing the conditions
    workflow = Path(__file__).parents[3] / "docs" / "userguide" / "workflow.md"
    assert "\n### Can my pull request be auto-merged?\n" in workflow.read_text()


async def test_auto_merge_comment_lists_the_approval_teams_once_in_a_collapsed_section(app):
    comment = await _render(app, _MANY_TEAMS)

    assert comment.count(_MANY_TEAMS) == 1
    assert comment.index("<details>") < comment.index(_MANY_TEAMS) < comment.index("</details>")
