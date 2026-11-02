#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

"""
The rules of rulesets that are modelled in addition to the pull request, status check, merge queue and deployment
rules: Copilot code review, metadata restrictions, push rules, code scanning, code quality, code coverage, license
compliance scanning and required workflows.
"""

from importlib.resources import files
from io import StringIO
from typing import Any
from unittest.mock import AsyncMock

import pytest
from pretend import stub

from otterdog.jsonnet import JsonnetConfig
from otterdog.models import FailureType, ValidationContext
from otterdog.models.organization_ruleset import OrganizationRuleset
from otterdog.models.repo_ruleset import RepositoryRuleset
from otterdog.models.ruleset import CodeScanningSettings
from otterdog.utils import IndentingPrinter, jsonnet_evaluate_snippet

ORG_ID = "my-org"
DEFAULTS = files("otterdog").joinpath("resources", "defaults", "otterdog-defaults.libsonnet")


def evaluate(expression: str) -> dict[str, Any]:
    return jsonnet_evaluate_snippet(f"local orgs = import '{DEFAULTS}'; {expression}")


def repo_ruleset(extension: str = "") -> RepositoryRuleset:
    return RepositoryRuleset.from_model_data(evaluate(f"orgs.newRepoRuleset('main') {{ {extension} }}"))


def org_ruleset(extension: str = "") -> OrganizationRuleset:
    return OrganizationRuleset.from_model_data(evaluate(f"orgs.newOrgRuleset('main') {{ {extension} }}"))


def provider_data(rules: list[dict[str, Any]], target: str = "branch") -> dict[str, Any]:
    return {
        "id": 1,
        "name": "main",
        "target": target,
        "enforcement": "active",
        "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
        "bypass_actors": [],
        "rules": rules,
    }


def validate(
    ruleset: RepositoryRuleset | OrganizationRuleset, plan: str = "enterprise"
) -> list[tuple[FailureType, str]]:
    context = ValidationContext(
        root_object=stub(settings=stub(plan=plan), repositories=[]),
        secret_resolver=stub(),
        template_dir="",
        org_members=set(),
        default_team_names=set(),
        exclude_teams_pattern=None,
    )
    parent = stub(get_model_header=lambda _=None: 'repository[name="my-repo"]', environments=[])
    ruleset.validate(context, parent)
    return context.validation_failures


def errors(ruleset: RepositoryRuleset | OrganizationRuleset, plan: str = "enterprise") -> list[str]:
    return [message for failure_type, message in validate(ruleset, plan) if failure_type == FailureType.ERROR]


def warnings(ruleset: RepositoryRuleset | OrganizationRuleset, plan: str = "enterprise") -> list[str]:
    return [message for failure_type, message in validate(ruleset, plan) if failure_type == FailureType.WARNING]


def github_provider(repo_ids: dict[str, int] | None = None):
    async def get_repo_ids(owner: str, names: list[str]) -> list[int]:
        return [(repo_ids or {})[f"{owner}/{name}"] for name in names]

    return stub(rest_api=stub(repo=stub(get_repo_ids=AsyncMock(side_effect=get_repo_ids))))


# the rules of branch rulesets supported by repository rulesets
REPOSITORY_RULES = """
    required_status_checks: null,
    copilot_code_review: orgs.newCopilotCodeReview() { review_on_push: true },
    commit_message_pattern: orgs.newPattern() { name: "issue", operator: "regex", pattern: "^#[0-9]+" },
    commit_author_email_pattern: orgs.newPattern() { operator: "ends_with", pattern: "@example.org" },
    committer_email_pattern: orgs.newPattern() { operator: "ends_with", pattern: "@example.org", negate: true },
    branch_name_pattern: orgs.newPattern() { operator: "starts_with", pattern: "feature/" },
    required_code_scanning: orgs.newCodeScanning() {
      code_scanning_tools+: ["CodeQL:high_or_higher:errors"],
    },
    required_code_quality: orgs.newCodeQuality() { severity: "warnings" },
    required_code_coverage: orgs.newCodeCoverage() { minimum_coverage: 80 },
    requires_license_compliance_scanning: true,
"""

# only supported by organization rulesets, its mapping is shared by all rulesets
REQUIRED_WORKFLOWS = """
    required_workflows: orgs.newWorkflows() {
      workflows+: [
        "my-org/.github:.github/workflows/build.yml@refs/heads/main",
        "my-org/.github:.github/workflows/lint.yml@0123456789abcdef0123456789abcdef01234567",
      ],
    },
"""

ALL_BRANCH_RULES = REPOSITORY_RULES + REQUIRED_WORKFLOWS

TEAM = "at least GitHub Team billing"
ENTERPRISE = "an 'enterprise' plan"

ALL_PUSH_RULES = """
    target: "push",
    allows_creations: true,
    allows_deletions: true,
    allows_force_pushes: true,
    required_pull_request: null,
    required_status_checks: null,
    restricted_file_paths+: ["secrets/**"],
    restricted_file_paths_exceptions+: ["secrets/README.md"],
    max_file_path_length: 255,
    restricted_file_extensions+: ["*.exe"],
    max_file_size: 10,
    max_file_size_exceptions+: ["assets/**"],
"""


class TestProviderMapping:
    def test_from_provider_reads_the_rules(self):
        rules = [
            {"type": "copilot_code_review", "parameters": {"review_on_push": True, "review_draft_pull_requests": True}},
            {"type": "commit_message_pattern", "parameters": {"operator": "regex", "pattern": "^#", "negate": False}},
            {
                "type": "code_scanning",
                "parameters": {
                    "code_scanning_tools": [
                        {"tool": "CodeQL", "security_alerts_threshold": "critical", "alerts_threshold": "none"}
                    ]
                },
            },
            {"type": "code_quality", "parameters": {"severity": "all"}},
            {"type": "code_coverage", "parameters": {"max_coverage_drop": 2.5}},
            {"type": "license_compliance_scanning"},
            {
                "type": "workflows",
                "parameters": {
                    "do_not_enforce_on_create": True,
                    "workflows": [
                        {
                            "repository_id": 42,
                            "repository_name": "my-org/.github",
                            "path": ".github/workflows/build.yml",
                            "ref": "refs/heads/main",
                        },
                        {"repository_id": 43, "path": ".github/workflows/lint.yml", "sha": "abc"},
                        {"repository_id": 44, "path": ".github/workflows/test.yml"},
                    ],
                },
            },
        ]

        ruleset = RepositoryRuleset.from_provider_data(ORG_ID, provider_data(rules))

        assert ruleset.copilot_code_review is not None
        assert ruleset.copilot_code_review.review_on_push is True
        assert ruleset.copilot_code_review.review_draft_pull_requests is True
        assert ruleset.commit_message_pattern is not None
        assert ruleset.commit_message_pattern.name == ""
        assert ruleset.commit_message_pattern.pattern == "^#"
        assert ruleset.branch_name_pattern is None
        assert ruleset.required_code_scanning is not None
        assert ruleset.required_code_scanning.code_scanning_tools == ["CodeQL:critical:none"]
        assert ruleset.required_code_quality is not None
        assert ruleset.required_code_quality.severity == "all"
        assert ruleset.required_code_coverage is not None
        assert ruleset.required_code_coverage.minimum_coverage is None
        assert ruleset.required_code_coverage.max_coverage_drop == 2.5
        assert ruleset.requires_license_compliance_scanning is True
        assert ruleset.required_workflows is not None
        assert ruleset.required_workflows.do_not_enforce_on_create is True
        # the repository is named by its id if its name could not be resolved
        assert ruleset.required_workflows.workflows == [
            "my-org/.github:.github/workflows/build.yml@refs/heads/main",
            "43:.github/workflows/lint.yml@abc",
            "44:.github/workflows/test.yml",
        ]

    def test_from_provider_reads_the_push_rules(self):
        rules = [
            {
                "type": "file_path_restriction",
                "parameters": {"restricted_file_paths": ["secrets/**"], "ignored_file_paths": ["secrets/README.md"]},
            },
            {"type": "max_file_path_length", "parameters": {"max_file_path_length": 255}},
            {"type": "file_extension_restriction", "parameters": {"restricted_file_extensions": ["*.exe"]}},
            {"type": "max_file_size", "parameters": {"max_file_size": 10}},
        ]

        ruleset = RepositoryRuleset.from_provider_data(ORG_ID, provider_data(rules, target="push"))

        assert ruleset.restricted_file_paths == ["secrets/**"]
        assert ruleset.restricted_file_paths_exceptions == ["secrets/README.md"]
        assert ruleset.max_file_path_length == 255
        assert ruleset.restricted_file_extensions == ["*.exe"]
        assert ruleset.max_file_size == 10
        assert ruleset.max_file_size_exceptions == []

    def test_from_provider_without_the_rules(self):
        ruleset = RepositoryRuleset.from_provider_data(ORG_ID, provider_data([]))

        for key in [
            "copilot_code_review",
            "commit_message_pattern",
            "commit_author_email_pattern",
            "committer_email_pattern",
            "branch_name_pattern",
            "tag_name_pattern",
            "required_code_scanning",
            "required_code_quality",
            "required_code_coverage",
            "required_workflows",
        ]:
            assert ruleset.__getattribute__(key) is None

        assert ruleset.restricted_file_paths == []
        assert ruleset.max_file_path_length == 0
        assert ruleset.max_file_size == 0
        assert ruleset.requires_license_compliance_scanning is False

    async def test_to_provider_writes_the_rules(self):
        ruleset = repo_ruleset(ALL_BRANCH_RULES)
        provider = github_provider({"my-org/.github": 42})

        data = await ruleset.to_provider_data(ORG_ID, provider)

        rules = {rule["type"]: rule.get("parameters") for rule in data["rules"]}
        assert rules["copilot_code_review"] == {"review_on_push": True, "review_draft_pull_requests": False}
        assert rules["commit_message_pattern"] == {
            "name": "issue",
            "negate": False,
            "operator": "regex",
            "pattern": "^#[0-9]+",
        }
        # an empty name is not sent, GitHub names the rule with its pattern
        assert "name" not in rules["commit_author_email_pattern"]
        assert rules["committer_email_pattern"]["negate"] is True
        assert rules["branch_name_pattern"]["pattern"] == "feature/"
        assert "tag_name_pattern" not in rules
        assert rules["code_scanning"] == {
            "code_scanning_tools": [
                {"tool": "CodeQL", "security_alerts_threshold": "high_or_higher", "alerts_threshold": "errors"}
            ]
        }
        assert rules["code_quality"] == {"severity": "warnings"}
        # an unset threshold is not sent
        assert rules["code_coverage"] == {"minimum_coverage": 80}
        assert "license_compliance_scanning" in rules
        assert rules["workflows"] == {
            "do_not_enforce_on_create": False,
            "workflows": [
                {"repository_id": 42, "path": ".github/workflows/build.yml", "ref": "refs/heads/main"},
                {
                    "repository_id": 42,
                    "path": ".github/workflows/lint.yml",
                    "sha": "0123456789abcdef0123456789abcdef01234567",
                },
            ],
        }
        # the repository of both workflows is only resolved once
        provider.rest_api.repo.get_repo_ids.assert_awaited_once_with("my-org", [".github"])

    async def test_to_provider_writes_the_push_rules(self):
        ruleset = repo_ruleset(ALL_PUSH_RULES)

        data = await ruleset.to_provider_data(ORG_ID, github_provider())

        assert data["rules"] == [
            {
                "type": "file_path_restriction",
                "parameters": {"restricted_file_paths": ["secrets/**"], "ignored_file_paths": ["secrets/README.md"]},
            },
            {"type": "max_file_path_length", "parameters": {"max_file_path_length": 255}},
            {"type": "file_extension_restriction", "parameters": {"restricted_file_extensions": ["*.exe"]}},
            {"type": "max_file_size", "parameters": {"max_file_size": 10, "ignored_file_paths": ["assets/**"]}},
        ]

    async def test_to_provider_omits_empty_exceptions_and_disabled_push_rules(self):
        ruleset = repo_ruleset('target: "push", restricted_file_paths+: ["secrets/**"]')

        data = await ruleset.to_provider_data(ORG_ID, github_provider())

        push_rules = [rule for rule in data["rules"] if rule["type"] in {"file_path_restriction", "max_file_size"}]
        assert push_rules == [
            {"type": "file_path_restriction", "parameters": {"restricted_file_paths": ["secrets/**"]}},
        ]

    async def test_to_provider_sends_no_rule_if_all_rules_are_disabled(self):
        # e.g. after disabling the last push rule, GitHub would keep it if the rules were not provided
        ruleset = repo_ruleset(
            'target: "push", allows_creations: true, allows_deletions: true, allows_force_pushes: true, '
            "required_pull_request: null, required_status_checks: null"
        )

        data = await ruleset.to_provider_data(ORG_ID, github_provider())

        assert data["rules"] == []

    async def test_to_provider_without_rules_in_the_data(self):
        mapping = await RepositoryRuleset.get_mapping_to_provider(ORG_ID, {"name": "main"}, github_provider())

        assert "rules" not in mapping

    def test_rules_missing_from_the_configuration_are_not_managed(self):
        # a template predating the rules does not define them, unlike null which disables a rule
        model_data = evaluate("orgs.newRepoRuleset('main') { required_status_checks: null }")
        for key in ["copilot_code_review", "required_code_scanning", "required_pull_request"]:
            model_data.pop(key)
        expected = RepositoryRuleset.from_model_data(model_data)
        live = repo_ruleset(
            """
            copilot_code_review: orgs.newCopilotCodeReview(),
            required_code_scanning: orgs.newCodeScanning() { code_scanning_tools+: ["CodeQL:all:all"] },
            required_status_checks: null,
            """
        )

        assert expected.get_difference_from(live) == {}
        assert set(repo_ruleset("required_status_checks: null").get_difference_from(live)) == {
            "copilot_code_review",
            "required_code_scanning",
        }

    async def test_to_provider_omits_the_ref_conditions_of_push_rulesets(self):
        ruleset = repo_ruleset(f'{ALL_PUSH_RULES} include_refs+: ["~DEFAULT_BRANCH"]')

        data = await ruleset.to_provider_data(ORG_ID, github_provider())

        assert data == {
            "name": "main",
            "target": "push",
            "enforcement": "active",
            "bypass_actors": [],
            "rules": [
                {
                    "type": "file_path_restriction",
                    "parameters": {
                        "restricted_file_paths": ["secrets/**"],
                        "ignored_file_paths": ["secrets/README.md"],
                    },
                },
                {"type": "max_file_path_length", "parameters": {"max_file_path_length": 255}},
                {"type": "file_extension_restriction", "parameters": {"restricted_file_extensions": ["*.exe"]}},
                {"type": "max_file_size", "parameters": {"max_file_size": 10, "ignored_file_paths": ["assets/**"]}},
            ],
        }

    async def test_to_provider_keeps_the_repository_conditions_of_organization_push_rulesets(self):
        ruleset = org_ruleset(f'{ALL_PUSH_RULES} include_repo_names+: ["~ALL"]')

        data = await ruleset.to_provider_data(ORG_ID, github_provider())

        assert data["conditions"] == {"repository_name": {"include": ["~ALL"], "exclude": [], "protected": False}}

    async def test_to_provider_keeps_the_ref_conditions_of_branch_rulesets(self):
        ruleset = org_ruleset('include_repo_names+: ["~ALL"], include_refs+: ["~DEFAULT_BRANCH"]')

        data = await ruleset.to_provider_data(ORG_ID, github_provider())

        assert data["conditions"] == {
            "ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []},
            "repository_name": {"include": ["~ALL"], "exclude": [], "protected": False},
        }

    async def test_code_scanning_tool_names_may_contain_colons(self):
        settings = {"code_scanning_tools": ["my:tool:all:all"]}

        data = await CodeScanningSettings.dict_to_provider_data(ORG_ID, settings, stub())

        assert data == {
            "code_scanning_tools": [{"tool": "my:tool", "security_alerts_threshold": "all", "alerts_threshold": "all"}]
        }

    @pytest.mark.parametrize("extension", [ALL_BRANCH_RULES, ALL_PUSH_RULES], ids=["branch", "push"])
    async def test_round_trip_has_no_difference(self, extension):
        expected = repo_ruleset(extension)
        provider = github_provider({"my-org/.github": 42})

        data = await expected.to_provider_data(ORG_ID, provider)
        # GitHub only returns the id of the repository of a workflow, its name is added when loading the ruleset
        for rule in data["rules"]:
            if rule["type"] == "workflows":
                for workflow in rule["parameters"]["workflows"]:
                    workflow["repository_name"] = "my-org/.github"

        live = RepositoryRuleset.from_provider_data(ORG_ID, {"id": 1, **data})

        assert expected.get_difference_from(live) == {}


class TestValidation:
    def test_valid_branch_ruleset(self):
        ruleset = repo_ruleset(REPOSITORY_RULES)

        assert errors(ruleset) == []
        assert warnings(ruleset) == []

    def test_required_workflows_in_repository_ruleset(self):
        ruleset = repo_ruleset(REQUIRED_WORKFLOWS)

        assert errors(ruleset) == [
            (
                f"{ruleset.get_model_header()} has 'required_workflows' set, "
                f"while it is only supported by organization rulesets."
            )
        ]

    @pytest.mark.parametrize(
        "plan,extension,expected_keys,requirement",
        [
            (
                "free",
                ALL_PUSH_RULES,
                ["restricted_file_paths", "max_file_path_length", "restricted_file_extensions", "max_file_size"],
                TEAM,
            ),
            ("free", "required_code_quality: orgs.newCodeQuality()", ["required_code_quality"], TEAM),
            (
                "free",
                "required_code_coverage: orgs.newCodeCoverage() { minimum_coverage: 1 }",
                ["required_code_coverage"],
                TEAM,
            ),
            ("team", ALL_PUSH_RULES, [], None),
            ("team", "required_code_quality: orgs.newCodeQuality()", [], None),
            ("free", "branch_name_pattern: orgs.newPattern() { pattern: 'x' }", ["branch_name_pattern"], ENTERPRISE),
            (
                "team",
                "commit_message_pattern: orgs.newPattern() { pattern: 'x' }",
                ["commit_message_pattern"],
                ENTERPRISE,
            ),
            (
                "team",
                "requires_license_compliance_scanning: true",
                ["requires_license_compliance_scanning"],
                ENTERPRISE,
            ),
            ("enterprise", REPOSITORY_RULES, [], None),
        ],
        ids=[
            "push_rules_free",
            "code_quality_free",
            "code_coverage_free",
            "push_rules_team",
            "code_quality_team",
            "pattern_free",
            "pattern_team",
            "license_compliance_team",
            "enterprise",
        ],
    )
    def test_rules_requiring_a_plan_trigger_warnings(self, plan, extension, expected_keys, requirement):
        ruleset = repo_ruleset(extension)

        assert warnings(ruleset, plan) == [
            f"{ruleset.get_model_header()} has '{key}' set, which requires {requirement}, currently using '{plan}' plan."
            for key in expected_keys
        ]
        # the rules only trigger warnings
        assert errors(ruleset, plan) == []

    def test_valid_push_ruleset(self):
        ruleset = repo_ruleset(ALL_PUSH_RULES)

        assert errors(ruleset) == []
        assert warnings(ruleset) == []

    def test_push_rules_require_target_push(self):
        result = errors(repo_ruleset('restricted_file_paths+: ["secrets/**"], max_file_size: 10'))

        assert len(result) == 2
        assert "'restricted_file_paths' set, while it is only supported by rulesets with target 'push'" in result[0]
        assert "'max_file_size' set, while it is only supported by rulesets with target 'push'" in result[1]

    def test_rules_not_supported_by_push_rulesets(self):
        ruleset = repo_ruleset(
            f"{ALL_PUSH_RULES} copilot_code_review: orgs.newCopilotCodeReview(), allows_updates: false"
        )

        assert errors(ruleset) == [
            (
                f"{ruleset.get_model_header()} has 'copilot_code_review' set, "
                f"while it is not supported by rulesets with target 'push'."
            )
        ]
        # the rules supported before the push rules only trigger a warning
        assert warnings(ruleset) == [
            (
                f"{ruleset.get_model_header()} requires the rule of 'allows_updates', "
                f"while it is not supported by rulesets with target 'push'."
            )
        ]

    def test_refs_of_push_rulesets_are_ignored(self):
        expected = repo_ruleset(f'{ALL_PUSH_RULES} include_refs+: ["~DEFAULT_BRANCH"]')
        live = repo_ruleset(ALL_PUSH_RULES)

        assert warnings(expected) == [
            f"{expected.get_model_header()} has 'include_refs' set, which is ignored by rulesets with target 'push'."
        ]
        assert expected.get_difference_from(live) == {}

    def test_push_ruleset_with_the_default_rules_triggers_warnings(self):
        result = warnings(repo_ruleset('target: "push", max_file_size: 10'))

        assert len(result) == 5
        for key in [
            "allows_creations",
            "allows_deletions",
            "allows_force_pushes",
            "required_pull_request",
            "required_status_checks",
        ]:
            assert any(f"'{key}'" in message for message in result)

    @pytest.mark.parametrize(
        "target,key",
        [("tag", "branch_name_pattern"), ("push", "branch_name_pattern"), ("branch", "tag_name_pattern")],
    )
    def test_ref_name_patterns_require_their_target(self, target, key):
        ruleset = repo_ruleset(
            f'target: "{target}", include_refs: [], {key}: orgs.newPattern() {{ pattern: "release-" }}'
        )

        assert any(
            f"'{key}' set, while it is only supported by rulesets with target" in message for message in errors(ruleset)
        )

    def test_tag_name_pattern_with_target_tag(self):
        ruleset = repo_ruleset('target: "tag", tag_name_pattern: orgs.newPattern() { pattern: "v" }')

        assert errors(ruleset) == []

    @pytest.mark.parametrize(
        "extension,expected",
        [
            ("max_file_size: 101", "'max_file_size' of value '101' while only integers in the range [0, 100]"),
            ("max_file_size: -1", "'max_file_size' of value '-1' while only integers in the range [0, 100]"),
            (
                "max_file_path_length: 32768",
                "'max_file_path_length' of value '32768' while only integers in the range [0, 32767]",
            ),
            (
                "restricted_file_extensions: ['*.%d' % x for x in std.range(1, 201)]",
                "'restricted_file_extensions' with 201 entries while at most 200 entries are allowed",
            ),
            (
                "restricted_file_paths: [std.join('', std.repeat(['a'], 201))]",
                "which is longer than 200 characters",
            ),
        ],
        ids=["file_size_too_large", "negative_file_size", "path_length_too_large", "too_many_entries", "too_long"],
    )
    def test_push_rule_limits(self, extension, expected):
        result = errors(repo_ruleset(f'target: "push", {extension}'))

        assert len(result) == 1
        assert expected in result[0]

    def test_exceptions_without_their_rule_are_ignored(self):
        expected = repo_ruleset(
            'target: "push", restricted_file_paths_exceptions+: ["a"], max_file_size_exceptions+: ["b"]'
        )
        live = repo_ruleset('target: "push"')

        result = warnings(expected)

        assert any("'restricted_file_paths_exceptions' set to '['a']' but 'restricted_file_paths'" in x for x in result)
        assert any("'max_file_size_exceptions' set to '['b']' but 'max_file_size'" in x for x in result)
        assert expected.get_difference_from(live) == {}

    def test_repository_only_rules_in_organization_ruleset(self):
        ruleset = org_ruleset(
            """
            required_code_quality: orgs.newCodeQuality(),
            required_code_coverage: orgs.newCodeCoverage() { minimum_coverage: 50 },
            requires_license_compliance_scanning: true,
            """
        )

        result = errors(ruleset)

        assert len(result) == 3
        for key in ["required_code_quality", "required_code_coverage", "requires_license_compliance_scanning"]:
            assert any(f"'{key}' set, while it is only supported by repository rulesets" in x for x in result)

    def test_organization_ruleset_with_the_other_rules(self):
        ruleset = org_ruleset(
            """
            copilot_code_review: orgs.newCopilotCodeReview(),
            required_code_scanning: orgs.newCodeScanning() { code_scanning_tools+: ["CodeQL:all:all"] },
            required_workflows: orgs.newWorkflows() { workflows+: ["my-org/.github:.github/workflows/ci.yml"] },
            """
        )

        assert errors(ruleset) == []

    @pytest.mark.parametrize(
        "extension,expected",
        [
            (
                "commit_message_pattern: orgs.newPattern() { operator: 'matches', pattern: 'x' }",
                (
                    "'commit_message_pattern.operator' of value 'matches', while only values ('starts_with' | "
                    "'ends_with' | 'contains' | 'regex') are allowed."
                ),
            ),
            (
                "committer_email_pattern: orgs.newPattern()",
                "has an empty 'committer_email_pattern.pattern'.",
            ),
            (
                "required_code_scanning: orgs.newCodeScanning()",
                "has an empty 'required_code_scanning.code_scanning_tools' while at least one tool must be required.",
            ),
            (
                "required_code_scanning: orgs.newCodeScanning() { code_scanning_tools+: ['CodeQL'] }",
                (
                    "containing value 'CodeQL' while only values of format "
                    "'tool:security_alerts_threshold:alerts_threshold' are allowed."
                ),
            ),
            (
                # the security alerts thresholds differ from the alerts thresholds
                "required_code_scanning: orgs.newCodeScanning() { code_scanning_tools+: ['CodeQL:errors:errors'] }",
                (
                    "with a security alerts threshold of value 'errors', while only values ('none' | 'critical' | "
                    "'high_or_higher' | 'medium_or_higher' | 'all') are allowed."
                ),
            ),
            (
                "required_code_scanning: orgs.newCodeScanning() { code_scanning_tools+: ['CodeQL:all:critical'] }",
                (
                    "with an alerts threshold of value 'critical', while only values ('none' | 'errors' | "
                    "'errors_and_warnings' | 'all') are allowed."
                ),
            ),
            (
                "required_code_quality: orgs.newCodeQuality() { severity: 'critical' }",
                (
                    "'required_code_quality.severity' of value 'critical', while only values ('errors' | 'warnings' | "
                    "'notes' | 'all') are allowed."
                ),
            ),
            (
                "required_code_coverage: orgs.newCodeCoverage() { minimum_coverage: 101 }",
                (
                    "'required_code_coverage.minimum_coverage' of value '101' while only percentages in the range "
                    "[0, 100] are allowed."
                ),
            ),
        ],
        ids=[
            "pattern_operator",
            "empty_pattern",
            "no_code_scanning_tool",
            "code_scanning_tool_format",
            "security_alerts_threshold",
            "alerts_threshold",
            "code_quality_severity",
            "code_coverage_range",
        ],
    )
    def test_invalid_settings(self, extension, expected):
        ruleset = repo_ruleset(extension)

        result = errors(ruleset)

        assert len(result) == 1
        # the message names the ruleset
        assert result[0].startswith(ruleset.get_model_header())
        assert expected in result[0]

    @pytest.mark.parametrize(
        "extension,expected",
        [
            (
                "required_workflows: orgs.newWorkflows()",
                "has an empty 'required_workflows.workflows' while at least one workflow must be required.",
            ),
            (
                "required_workflows: orgs.newWorkflows() { workflows+: ['.github:.github/workflows/ci.yml'] }",
                (
                    "containing value '.github:.github/workflows/ci.yml' while only values of format "
                    "'owner/repository:path[@ref]' are allowed."
                ),
            ),
            (
                # a repository that could not be resolved when loading the ruleset
                "required_workflows: orgs.newWorkflows() { workflows+: ['42:.github/workflows/ci.yml'] }",
                (
                    "containing value '42:.github/workflows/ci.yml' whose repository with id '42' could not be "
                    "resolved, while a repository must be referenced by its full name 'owner/repository'."
                ),
            ),
        ],
        ids=["no_workflow", "workflow_format", "unresolved_repository"],
    )
    def test_invalid_required_workflows(self, extension, expected):
        ruleset = org_ruleset(extension)

        result = errors(ruleset)

        assert len(result) == 1
        assert result[0].startswith(ruleset.get_model_header())
        assert expected in result[0]

    def test_code_coverage_without_threshold_triggers_a_warning(self):
        ruleset = repo_ruleset("required_code_coverage: orgs.newCodeCoverage()")

        assert errors(ruleset) == []
        assert any("the rule has no effect" in message for message in warnings(ruleset))


class TestJsonnet:
    @staticmethod
    def jsonnet_config():
        names = {key: value for key, value in vars(JsonnetConfig).items() if key.startswith("create_")}
        defaults = {
            "default_pull_request_config": evaluate("orgs.newPullRequest()"),
            "default_status_checks_config": evaluate("orgs.newStatusChecks()"),
            "default_merge_queue_config": evaluate("orgs.newMergeQueue()"),
            "default_copilot_code_review_config": evaluate("orgs.newCopilotCodeReview()"),
            "default_pattern_config": evaluate("orgs.newPattern()"),
            "default_code_scanning_config": evaluate("orgs.newCodeScanning()"),
            "default_code_quality_config": evaluate("orgs.newCodeQuality()"),
            "default_code_coverage_config": evaluate("orgs.newCodeCoverage()"),
            "default_workflows_config": evaluate("orgs.newWorkflows()"),
        }
        return stub(**names, **defaults)

    def import_ruleset(self, live: RepositoryRuleset, default: RepositoryRuleset, jsonnet_config) -> str:
        output = StringIO()
        live.to_jsonnet(IndentingPrinter(output), jsonnet_config, stub(), False, default)
        return output.getvalue().strip().rstrip(",")

    def test_import_narrows_the_default_lists(self):
        # a template requiring CodeQL and Semgrep by default, while the live ruleset only requires CodeQL
        extension = """
            required_code_scanning: orgs.newCodeScanning() {
              code_scanning_tools+: ["CodeQL:all:all", "Semgrep:all:all"],
            },
            required_workflows: orgs.newWorkflows() {
              workflows+: ["my-org/.github:a.yml", "my-org/.github:b.yml"],
            },
        """
        default = repo_ruleset(extension)
        live = repo_ruleset(
            """
            required_code_scanning: orgs.newCodeScanning() { code_scanning_tools+: ["CodeQL:all:all"] },
            required_workflows: orgs.newWorkflows() { workflows+: ["my-org/.github:a.yml"] },
            """
        )

        jsonnet = self.import_ruleset(live, default, self.jsonnet_config())

        assert "code_scanning_tools: [" in jsonnet
        assert "workflows: [" in jsonnet
        # evaluated with the template whose rulesets require these lists by default
        template = (
            f"local defaults = import '{DEFAULTS}'; "
            f"local orgs = defaults {{ newRepoRuleset(name):: defaults.newRepoRuleset(name) {{ {extension} }} }}; "
        )
        imported = RepositoryRuleset.from_model_data(jsonnet_evaluate_snippet(template + jsonnet))
        assert imported.get_difference_from(live) == {}

    def test_import_without_the_function_of_a_rule_in_the_template(self):
        # a template predating the rule, e.g. pinned to an older version of otterdog
        jsonnet_config = self.jsonnet_config()
        jsonnet_config.default_copilot_code_review_config = None
        live = repo_ruleset("copilot_code_review: orgs.newCopilotCodeReview() { review_on_push: true }")

        jsonnet = self.import_ruleset(live, repo_ruleset(), jsonnet_config)

        assert "newCopilotCodeReview" not in jsonnet
        imported = RepositoryRuleset.from_model_data(evaluate(jsonnet))
        assert imported.get_difference_from(live) == {}

    @pytest.mark.parametrize(
        "extension",
        [
            ALL_BRANCH_RULES,
            ALL_PUSH_RULES,
            # settings that equal their default values must not be lost
            "copilot_code_review: orgs.newCopilotCodeReview(), required_merge_queue: orgs.newMergeQueue()",
        ],
        ids=["branch", "push", "default_settings"],
    )
    def test_import_round_trip_has_no_difference(self, extension):
        live = repo_ruleset(extension)
        output = StringIO()

        live.to_jsonnet(IndentingPrinter(output), self.jsonnet_config(), stub(), False, repo_ruleset())

        imported = RepositoryRuleset.from_model_data(evaluate(output.getvalue().strip().rstrip(",")))
        assert imported.get_difference_from(live) == {}
        assert live.get_difference_from(imported) == {}
