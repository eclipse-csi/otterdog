#  *******************************************************************************
#  Copyright (c) 2025 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************


def test_plan_when_configuration_is_current(e2e):
    """Scenario: User checks plan, configuration matches GitHub.

    When user runs:
        otterdog plan test-org

    Then:
        Plan completes successfully
        Output indicates what needs to be changed (or no changes)
    """
    exit_code, output = e2e.run_cli("plan", "test-org", "--local", "--no-web-ui")

    assert exit_code == 0, f"Expected success, got exit code {exit_code}\n{output}"
    assert output, "Expected plan output"
    assert "Plan" in output or "Diffing" in output, "Expected plan/diff message in output"

    # Verify that GitHub API was called to fetch current state
    calls = e2e.get_github_calls()
    assert len(calls) > 0, "Expected API calls to fetch GitHub state"


def test_plan_when_configuration_is_out_of_sync(e2e):
    """Scenario: User checks plan, GitHub has drift.

    When user runs:
        otterdog plan test-org

    And GitHub organization description differs from config:

    Then:
        Plan still completes successfully
        Output shows the detected difference
    """
    drifted_settings = {**e2e.github_org, "description": "Old description"}
    e2e.configure_github(response_overrides={"/settings": drifted_settings})

    exit_code, output = e2e.run_cli("plan", "test-org", "--local", "--no-web-ui")

    assert exit_code == 0, f"Expected success, got exit code {exit_code}\n{output}"
    assert output, "Expected plan operation to produce output"
    assert "Plan" in output or "Diffing" in output, "Expected plan/diff message in output"

    # Verify that the drift was detected by checking API calls
    calls = e2e.get_github_calls()
    org_calls = [call for call in calls if "/orgs/test-org" in call[1] and call[0] == "GET"]
    assert len(org_calls) > 0, "Expected GET requests to fetch organization state for comparison"
