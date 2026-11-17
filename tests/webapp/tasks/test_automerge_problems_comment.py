#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from pathlib import Path

from quart import render_template


async def test_automerge_problems_comment_links_to_what_to_do(app):
    async with app.app_context():
        comment = await render_template(
            "comment/automerge_problems.txt",
            problems=["pull request is not valid, check the `/otterdog validate` comment for details and push a fix"],
        )

    assert "pull request is not valid" in comment
    link = f"({app.config['DOCUMENTATION_URL']}userguide/guides/troubleshooting/#merging-with-otterdog-merge)"
    assert link in comment

    # the section of the documentation explaining the problems
    troubleshooting = Path(__file__).parents[3] / "docs" / "userguide" / "guides" / "troubleshooting.md"
    assert "\n## Merging with `/otterdog merge`\n" in troubleshooting.read_text()
