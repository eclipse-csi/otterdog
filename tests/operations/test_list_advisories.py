#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import pretend
import pytest

from otterdog.operations.list_advisories import ListAdvisoriesOperation


class TestListAdvisoriesOperation:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "advisory_data,expected_values",
        [
            (
                {
                    "cve_id": "CVE-2024-1234",
                    "summary": "Test advisory",
                },
                {
                    "cve": "CVE-2024-1234",
                    "summary_check": '"Test advisory"',
                },
            ),
            (
                {
                    "cve_id": None,
                    "summary": "Advisory without CVE",
                },
                {
                    "cve": "NO_CVE",
                    "summary_check": '"Advisory without CVE"',
                },
            ),
            (
                {
                    "cve_id": "",
                    "summary": "Empty CVE advisory",
                },
                {
                    "cve": "",
                    "summary_check": '"Empty CVE advisory"',
                },
            ),
            (
                {
                    "cve_id": "CVE-2024-5555",
                    "summary": 'Summary with "quotes" and more "text"',
                },
                {
                    "cve": "CVE-2024-5555",
                    "summary_check": '"Summary with ""quotes"" and more ""text"""',
                },
            ),
        ],
    )
    async def test_execute_advisory_processing(self, advisory_data, expected_values, monkeypatch, mock_github_provider):
        operation = ListAdvisoriesOperation(states=["published"], details=False)

        base_advisory = {
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-02T00:00:00Z",
            "published_at": "2024-01-03T00:00:00Z",
            "state": "published",
            "severity": "high",
            "ghsa_id": "GHSA-1234",
            "html_url": "https://github.com/advisories/GHSA-1234",
        }
        test_advisory = {**base_advisory, **advisory_data}

        operation.printer = pretend.stub(
            println=pretend.call_recorder(lambda msg: None),
            level_up=lambda: None,
            level_down=lambda: None,
        )
        operation.get_credentials = lambda *args, **kwargs: "test-token"
        operation._print_project_header = lambda *args: None

        mock_provider = mock_github_provider()
        mock_provider.setup_org_advisories({"published": [test_advisory]})

        monkeypatch.setattr("otterdog.operations.list_advisories.GitHubProvider", lambda *args: mock_provider)
        monkeypatch.setattr("otterdog.operations.list_advisories.is_info_enabled", lambda: False)
        monkeypatch.setattr("otterdog.operations.list_advisories.format_date_for_csv", lambda x: x[:10])

        org_config = pretend.stub(name="test-org", github_id="test-github-id")

        result = await operation.execute(org_config)

        assert result == 0
        assert len(operation.printer.println.calls) == 1

        csv_output = operation.printer.println.calls[0].args[0]
        assert f'"{expected_values["cve"]}"' in csv_output
        assert expected_values["summary_check"] in csv_output
        assert '"GHSA-1234"' in csv_output
        assert '"test-org"' in csv_output

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "states,advisories_config",
        [
            # Single state, multiple advisories
            (
                ["published"],
                {
                    "published": [
                        {"ghsa_id": "GHSA-1111", "cve_id": "CVE-1111"},
                        {"ghsa_id": "GHSA-2222", "cve_id": "CVE-2222"},
                    ]
                },
            ),
            # Multiple states, one advisory each
            (
                ["published", "closed"],
                {
                    "published": [{"ghsa_id": "GHSA-3333", "cve_id": "CVE-3333"}],
                    "closed": [{"ghsa_id": "GHSA-4444", "cve_id": "CVE-4444"}],
                },
            ),
            # Multiple states, mixed counts
            (
                ["triage", "draft", "published"],
                {
                    "triage": [],
                    "draft": [{"ghsa_id": "GHSA-5555", "cve_id": None}],
                    "published": [
                        {"ghsa_id": "GHSA-6666", "cve_id": "CVE-6666"},
                        {"ghsa_id": "GHSA-7777", "cve_id": "CVE-7777"},
                    ],
                },
            ),
        ],
    )
    async def test_execute_multiple_states_and_advisories(
        self, states, advisories_config, monkeypatch, mock_github_provider
    ):
        operation = ListAdvisoriesOperation(states=states, details=False)

        operation.printer = pretend.stub(
            println=pretend.call_recorder(lambda msg: None),
            level_up=lambda: None,
            level_down=lambda: None,
        )
        operation.get_credentials = lambda *args, **kwargs: "test-token"
        operation._print_project_header = lambda *args: None

        full_advisories = {}
        for state, advisories in advisories_config.items():
            full_advisories[state] = []
            for adv in advisories:
                base = {
                    "created_at": "2024-01-01T00:00:00Z",
                    "updated_at": "2024-01-02T00:00:00Z",
                    "published_at": "2024-01-03T00:00:00Z",
                    "state": state,
                    "severity": "high",
                    "html_url": f"https://github.com/advisories/{adv['ghsa_id']}",
                    "summary": f"Advisory {adv['ghsa_id']}",
                }
                full_advisories[state].append({**base, **adv})

        mock_provider = mock_github_provider()
        mock_provider.setup_org_advisories(full_advisories)

        monkeypatch.setattr("otterdog.operations.list_advisories.GitHubProvider", lambda *args: mock_provider)
        monkeypatch.setattr("otterdog.operations.list_advisories.is_info_enabled", lambda: False)
        monkeypatch.setattr("otterdog.operations.list_advisories.format_date_for_csv", lambda x: x[:10])

        org_config = pretend.stub(name="test-org", github_id="test-github-id")

        result = await operation.execute(org_config)

        assert result == 0

        total_advisories = sum(len(advs) for advs in advisories_config.values())
        assert len(operation.printer.println.calls) == total_advisories

        csv_outputs = [call.args[0] for call in operation.printer.println.calls]
        for advisories in advisories_config.values():
            for adv in advisories:
                assert any(f'"{adv["ghsa_id"]}"' in output for output in csv_outputs)
