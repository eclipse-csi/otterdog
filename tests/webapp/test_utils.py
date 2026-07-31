#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from datetime import timedelta

from otterdog.webapp.utils import (
    backoff_if_needed,
    contains_team_matching_approval_pattern,
    current_utc_time,
    describe_approval_teams,
    get_approval_team_patterns,
    team_matches_approval_pattern,
)


async def test_backoff_if_needed():
    # check that we wait the required timeout period
    start = current_utc_time()
    await backoff_if_needed(start, timedelta(seconds=3))
    end = current_utc_time()
    assert end - start > timedelta(seconds=3)

    # check that we do not wait if the required timeout already expired
    start = current_utc_time()
    await backoff_if_needed(start - timedelta(seconds=60), timedelta(seconds=3))
    end = current_utc_time()
    assert end - start < timedelta(seconds=1)


async def test_get_approval_team_patterns_splits_and_strips_entries(app):
    async with app.app_context():
        app.config["GITHUB_APPROVAL_TEAMS"] = " project-leads , .*-committers$ "
        assert get_approval_team_patterns() == ["project-leads", ".*-committers$"]

        app.config["GITHUB_APPROVAL_TEAMS"] = "project-leads$"
        assert get_approval_team_patterns() == ["project-leads$"]


async def test_team_matches_approval_pattern_with_literal_and_regex_entries(app):
    async with app.app_context():
        app.config["GITHUB_APPROVAL_TEAMS"] = "project-leads,.*-committers$"

        assert team_matches_approval_pattern("org/project-leads") is True
        assert team_matches_approval_pattern("org/example-committers") is True
        assert team_matches_approval_pattern("org/some-other-team") is False

        # Invalid regex entries should be ignored (and must not crash matching)
        app.config["GITHUB_APPROVAL_TEAMS"] = "(,project-leads$"
        assert team_matches_approval_pattern("org/project-leads") is True


async def test_contains_team_matching_approval_pattern(app):
    async with app.app_context():
        app.config["GITHUB_APPROVAL_TEAMS"] = "project-leads$"

        assert contains_team_matching_approval_pattern(["org/some-team", "org/project-leads"]) is True
        assert contains_team_matching_approval_pattern(["org/some-team", "org/other-team"]) is False
        assert contains_team_matching_approval_pattern([]) is False


async def test_describe_approval_teams(app):
    async with app.app_context():
        app.config["GITHUB_APPROVAL_TEAMS"] = "project-leads$"

        assert describe_approval_teams(None) == "a team matching pattern 'project-leads$'"
        assert describe_approval_teams(["org/project-leads"]) == "team 'org/project-leads'"
        assert describe_approval_teams(["org/team-a", "org/team-b"]) == "team 'org/team-a' or 'org/team-b'"
        assert describe_approval_teams([]) == (
            "a team matching pattern 'project-leads$' "
            "(no team in this organization currently matches any of these patterns)"
        )


async def test_describe_approval_teams_with_multiple_patterns(app):
    async with app.app_context():
        app.config["GITHUB_APPROVAL_TEAMS"] = "project-leads$,.*-committers$"

        assert describe_approval_teams(None) == "a team matching patterns 'project-leads$' or '.*-committers$'"
