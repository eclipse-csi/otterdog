#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from pathlib import Path

from quart import render_template

from otterdog.webapp.tasks.auto_merge_comment import with_auto_merge_status

# some organizations have dozens of approval teams
_MANY_TEAMS = "team " + " or ".join(f"'project-{i}-leads'" for i in range(60))


async def _render(app, template: str, **context) -> str:
    async with app.app_context():
        return await render_template(template, **context)


async def _render_status(app, team_description: str) -> str:
    return await _render(
        app,
        "comment/auto_merge_status.txt",
        team_description=team_description,
        admin_team_description="team 'org/otterdog-admins'",
    )


async def test_status_tells_who_can_merge_and_how(app):
    status = await _render_status(app, "team 'project-leads'")

    assert status.startswith("### :rocket: Ready to merge\n")

    # the command comes first, in a code block that can be copied
    assert "```\n/otterdog merge\n```" in status
    assert status.index("/otterdog merge") < status.index("<details>")

    assert (
        "The author of the pull request, or a member of an approval team or of an admin team, can run this command."
        in status
    )
    assert "the changes add or change no secret and no webhook that has a secret" in status

    link = f"({app.config['DOCUMENTATION_URL']}userguide/workflow/#can-my-pull-request-be-auto-merged)"
    assert link in status

    # the section of the documentation listing the conditions
    workflow = Path(__file__).parents[3] / "docs" / "userguide" / "workflow.md"
    assert "\n### Can my pull request be auto-merged?\n" in workflow.read_text()


async def test_status_lists_the_approval_teams_once_in_a_collapsed_section(app):
    status = await _render_status(app, _MANY_TEAMS)

    assert status.count(_MANY_TEAMS) == 1
    assert status.index("<details>") < status.index(_MANY_TEAMS) < status.index("</details>")
    # the admin teams can merge it too
    assert "\n**Admin teams**: team 'org/otterdog-admins'\n" in status


async def test_status_is_shown_at_the_top_of_the_validation_comment(app):
    comment = await _render(
        app,
        "comment/validation_comment.txt",
        sha="head-sha",
        result="Plan: 0 to add, 1 to change, 0 to delete.",
        admin_teams=["test-org/admins"],
        warnings=[],
        auto_merge_blockers=[],
    )
    status = await _render_status(app, "team 'project-leads'")

    with_status = with_auto_merge_status(comment, status)

    assert with_status is not None
    assert with_status.startswith("<!-- Otterdog Comment: validate -->\n")
    assert with_status.index("### :rocket: Ready to merge") < with_status.index("Please find below the validation")
    # the status is removed again without altering the rest of the comment
    assert with_auto_merge_status(with_status, "") == comment
    assert with_auto_merge_status(comment, "") == comment


def test_comment_without_a_status_section_cannot_show_it():
    assert with_auto_merge_status("<!-- Otterdog Comment: validate -->\nPlease find below", "status") is None


async def test_merge_refusal_lists_the_teams_once_in_a_collapsed_section(app):
    refusal = await _render(
        app,
        "comment/automerge_eligibility.txt",
        team_description=_MANY_TEAMS,
        admin_team_description="team 'org/otterdog-admins'",
        author_status="The author is not a member of an approval or admin team",
        approval_status="No approval from a member of an approval or admin team was found",
    )

    assert refusal.count(_MANY_TEAMS) == 1
    teams_section = refusal.index("<summary>Approval and admin teams</summary>")
    assert teams_section < refusal.index(_MANY_TEAMS) < refusal.index("</details>", teams_section)
    assert "- **Admin teams**: team 'org/otterdog-admins'\n" in refusal
