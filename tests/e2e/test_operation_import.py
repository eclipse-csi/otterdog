#  *******************************************************************************
#  Copyright (c) 2025 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************


def test_import_creates_jsonnet_file(e2e):
    """Scenario: User imports GitHub state to create Jsonnet config.

    When user runs:
        otterdog import-config test-org

    Then:
        Import completes successfully
        Output indicates configuration was imported
    """
    exit_code, output = e2e.run_cli("import", "test-org", "--force", "--local", "--no-web-ui", "-vv")

    assert exit_code == 0, f"Expected success, got exit code {exit_code}\n{output}"
    assert output, "Expected import operation to produce output"
    assert "Importing resources" in output, "Expected 'Importing resources' message"
    assert "test-org" in output, "Expected organization name in output"
    
    # Verify that GitHub API was called to fetch organization data
    calls = e2e.get_github_calls()
    org_calls = [call for call in calls if "/orgs/test-org" in call[1]]
    assert len(org_calls) > 0, "Expected API calls to fetch organization data"


def test_import_with_drifted_settings(e2e):
    """Scenario: User imports when GitHub differs from previous config.

    When user runs:
        otterdog import-config test-org

    And GitHub organization description differs:

    Then:
        Import completes successfully
        New configuration reflects current GitHub state
    """
    drifted_settings = {**e2e.github_org, "description": "Current GitHub description"}
    e2e.configure_github(response_overrides={"/settings": drifted_settings})

    exit_code, output = e2e.run_cli("import", "test-org", "--force", "--local", "--no-web-ui")

    assert exit_code == 0, f"Expected success, got exit code {exit_code}\n{output}"
    assert output, "Expected import operation to produce output"
    assert "Importing resources" in output, "Expected 'Importing resources' message"
    
    # Verify the drifted description was fetched
    calls = e2e.get_github_calls()
    org_settings_call = any("/orgs/test-org" in call[1] and call[0] == "GET" for call in calls)
    assert org_settings_call, "Expected GET request to fetch organization settings"
