#  *******************************************************************************
#  Copyright (c) 2025 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************


def test_apply_when_no_changes_needed(e2e):
    exit_code, output = e2e.run_cli("apply", "test-org", "--force", "--local", "--no-web-ui")

    assert exit_code == 0, f"Expected success, got exit code {exit_code}\n{output}"
    assert output, "Expected output from apply command"
    # For now, accept any exit code - the important thing is the test infrastructure works


def test_apply_with_setting_change(e2e):
    drifted_settings = {**e2e.github_org, "description": "Old description"}
    e2e.configure_github(response_overrides={"/settings": drifted_settings})

    exit_code, output = e2e.run_cli("apply", "test-org", "--force", "--local", "--no-web-ui")

    assert exit_code == 0, f"Expected success, got exit code {exit_code}\n{output}"
    assert output, "Expected output from apply command"

    # Verify that a PATCH request was made to update the settings
    calls = e2e.get_github_calls()
    patch_calls = [call for call in calls if call[0] == "PATCH"]
    assert len(patch_calls) > 0, "Expected at least one PATCH request to update settings"
