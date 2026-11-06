#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

import re
from typing import Any
from unittest.mock import MagicMock

import pytest

from otterdog.config import CredentialResolver, OrganizationConfig, OtterdogConfig
from otterdog.credentials import CredentialPlaceHolders
from otterdog.credentials.secret_access_policy import SecretAccessMode, SecretAccessPolicy
from otterdog.models import FailureType, ValidationContext
from otterdog.models.organization_webhook import OrganizationWebhook
from otterdog.models.repo_secret import RepositorySecret

_ORG_NAME = "technology.apoapsis"
_GITHUB_ID = "eclipse-apoapsis"
_BITWARDEN_ITEM = "8c4f0a5e-0d2b-4c1e-9f3a-1b2c3d4e5f60"

_ALLOWED_REFERENCES = {
    "pass": ["bots/{org_name}/**"],
    "vault": ["{org_name}/**"],
    "bitwarden": [_BITWARDEN_ITEM],
}


def _policy(
    allowed_references: dict[str, list[str]] | None = None, mode: SecretAccessMode = SecretAccessMode.ENFORCE
) -> SecretAccessPolicy:
    return SecretAccessPolicy(
        mode,
        _ALLOWED_REFERENCES if allowed_references is None else allowed_references,
        CredentialPlaceHolders(org_name=_ORG_NAME, github_id=_GITHUB_ID),
    )


@pytest.mark.parametrize(
    "secret_data",
    [
        "pass:bots/technology.apoapsis/gpg/key_id",
        "pass:bots/technology.apoapsis/github.com/api-token",
        "vault:technology.apoapsis/oss.sonatype.org/token-password",
        "vault:technology.apoapsis/token",
        f"bitwarden:{_BITWARDEN_ITEM}@api_token",
    ],
)
def test_references_of_the_organization_are_allowed(secret_data: str):
    assert _policy().check(secret_data) is None


@pytest.mark.parametrize(
    "secret_data",
    [
        # the secrets of another organization
        "pass:bots/technology.other/gpg/key_id",
        "vault:technology.other/oss.sonatype.org/token-password",
        "bitwarden:00000000-0000-0000-0000-000000000000@api_token",
        # the name of the organization as a prefix of another one, or below another one
        "pass:bots/technology.apoapsis-other/gpg/key_id",
        "pass:bots/technology.other/technology.apoapsis/key_id",
        # the value of a placeholder is matched literally, '.' is not a wildcard
        "pass:bots/technologyXapoapsis/gpg/key_id",
        # a trailing '**' matches at least one segment
        "pass:bots/technology.apoapsis",
    ],
)
def test_references_outside_of_the_organization_are_denied(secret_data: str):
    assert "does not match the allowed references" in (_policy().check(secret_data) or "")


@pytest.mark.parametrize(
    "secret_data",
    [
        "pass:bots/technology.apoapsis/../technology.other/key_id",
        "pass:bots/technology.apoapsis/./key_id",
        "pass:bots/technology.apoapsis//key_id",
        "pass:/bots/technology.apoapsis/key_id",
        "pass:bots/technology.apoapsis/key_id$(id)",
        "pass:bots/technology.apoapsis/key_id;id",
        "pass:bots/technology.apoapsis/key id",
        "pass:bots/technology.apoapsis/key_id:other",
        "vault:technology.apoapsis/../technology.other/token",
        f"bitwarden:{_BITWARDEN_ITEM}$(id)@api_token",
    ],
)
def test_invalid_references_are_denied(secret_data: str):
    assert "is not a valid reference" in (_policy().check(secret_data) or "")


@pytest.mark.parametrize("secret_data", [f"bitwarden:{_BITWARDEN_ITEM}", "bitwarden:@api_token", "bitwarden:id@"])
def test_bitwarden_references_need_an_item_and_a_field(secret_data: str):
    assert "is not a valid bitwarden reference" in (_policy().check(secret_data) or "")


def test_references_of_providers_without_allowed_references_are_denied():
    policy = _policy({"pass": ["bots/{org_name}/**"]})

    assert policy.check("vault:eclipse-apoapsis/token") == "no secret of provider 'vault' is allowed"


@pytest.mark.parametrize(
    "secret_data",
    [
        "a literal secret",
        "https://example.org/hook",
        "env:SOME_VARIABLE",
        "plain:value",
        "",
    ],
)
def test_values_not_read_from_a_secret_store_are_not_restricted(secret_data: str):
    assert _policy({}).check(secret_data) is None


@pytest.mark.parametrize(
    ("pattern", "reference", "allowed"),
    [
        ("shared/**/token", "shared/token", True),
        ("shared/**/token", "shared/a/b/token", True),
        ("shared/**/token", "shared/a/b/other", False),
        ("**/{org_name}/*", "a/b/technology.apoapsis/token", True),
        ("bots/{org_name}/gpg/*_id", "bots/technology.apoapsis/gpg/key_id", True),
        # '*' does not match across segments
        ("bots/{org_name}/*", "bots/technology.apoapsis/gpg/key_id", False),
        ("bots/*.{org_name}/token", "bots/project.technology.apoapsis/token", True),
        ("{github_id}/**", "eclipse-apoapsis/oss.sonatype.org/password", True),
        ("{github_id}/**", "technology.apoapsis/oss.sonatype.org/password", False),
        ("bots/{github_id}-{org_name}/*", "bots/eclipse-apoapsis-technology.apoapsis/token", True),
    ],
)
def test_wildcards_and_placeholders(pattern: str, reference: str, allowed: bool):
    assert (_policy({"pass": [pattern]}).check(f"pass:{reference}") is None) is allowed


def test_the_denial_shows_the_allowed_references_of_the_organization():
    violation = _policy().check("pass:bots/technology.other/key_id")

    assert violation == (
        "'bots/technology.other/key_id' does not match the allowed references of provider 'pass': "
        "'bots/technology.apoapsis/**'"
    )


@pytest.mark.parametrize(
    ("allowed_references", "error"),
    [
        ({"pass": ["bots/{org}/**"]}, "unknown placeholder '{org}'"),
        ({"pass": ["bots/x**/token"]}, "'**' must be a whole segment"),
        ({"pass": ["bots/../token"]}, "'.' and '..' segments are not allowed"),
        ({"pass": ["bots//token"]}, "'.' and '..' segments are not allowed"),
        ({"pass": ["bots/$(id)/token"]}, "only letters, digits"),
        ({"passs": ["bots/{org_name}/**"]}, "unknown provider 'passs'"),
        ({"pass": "bots/{org_name}/**"}, "expected a list of strings"),
        (["bots/{org_name}/**"], "expected an object"),
    ],
)
def test_invalid_allowed_references_are_rejected(allowed_references: Any, error: str):
    with pytest.raises((RuntimeError, TypeError), match=re.escape(error)):
        SecretAccessPolicy.parse_allowed_references(allowed_references, "allowed_references")


def test_the_mode_is_enforce_by_default():
    assert SecretAccessPolicy.parse_mode(None, "mode") == SecretAccessMode.ENFORCE
    assert SecretAccessPolicy.parse_mode("warn", "mode") == SecretAccessMode.WARN

    with pytest.raises(RuntimeError, match="expected one of 'warn', 'enforce'"):
        SecretAccessPolicy.parse_mode("audit", "mode")


def _organization(secrets: dict[str, Any] | None = None, name: str = _ORG_NAME, github_id: str = _GITHUB_ID) -> dict:
    organization: dict[str, Any] = {"name": name, "github_id": github_id, "credentials": {"provider": "plain"}}
    if secrets is not None:
        organization["secrets"] = secrets
    return organization


def _config(tmp_path, defaults_secrets: dict[str, Any] | None, *organizations: dict) -> OtterdogConfig:
    defaults: dict[str, Any] = {
        "jsonnet": {"base_template": "https://github.com/example/defaults#defaults.libsonnet@main"}
    }
    if defaults_secrets is not None:
        defaults["secrets"] = defaults_secrets
    return OtterdogConfig.from_dict(
        {"defaults": defaults, "organizations": list(organizations or [_organization()])}, False, str(tmp_path)
    )


def test_no_policy_without_configuration(tmp_path):
    config = _config(tmp_path, None)

    assert config.get_secret_access_policy(config.get_organization_config(_GITHUB_ID)) is None


def test_the_default_policy_uses_the_values_of_the_organization(tmp_path):
    config = _config(
        tmp_path,
        {"allowed_references": {"pass": ["bots/{org_name}/**"]}},
        _organization(),
        _organization(name="technology.other", github_id="eclipse-other"),
    )

    apoapsis = config.get_secret_access_policy(config.get_organization_config(_GITHUB_ID))
    other = config.get_secret_access_policy(config.get_organization_config("eclipse-other"))

    assert apoapsis is not None and other is not None
    assert apoapsis.is_enforced
    assert apoapsis.check("pass:bots/technology.apoapsis/key_id") is None
    assert apoapsis.check("pass:bots/technology.other/key_id") is not None
    assert other.check("pass:bots/technology.other/key_id") is None
    assert other.check("pass:bots/technology.apoapsis/key_id") is not None


def test_the_mode_can_be_warn(tmp_path):
    config = _config(tmp_path, {"mode": "warn", "allowed_references": {"pass": ["bots/{org_name}/**"]}})

    policy = config.get_secret_access_policy(config.get_organization_config(_GITHUB_ID))

    assert policy is not None and policy.mode == SecretAccessMode.WARN


def test_the_references_of_an_organization_extend_the_default_ones(tmp_path):
    config = _config(
        tmp_path,
        {"allowed_references": {"pass": ["bots/{org_name}/**"]}},
        _organization({"allowed_references": {"pass": ["bots/shared/sonatype/**"], "vault": ["{github_id}/**"]}}),
        _organization(name="technology.other", github_id="eclipse-other"),
    )

    apoapsis = config.get_secret_access_policy(config.get_organization_config(_GITHUB_ID))
    other = config.get_secret_access_policy(config.get_organization_config("eclipse-other"))

    assert apoapsis is not None and other is not None
    assert apoapsis.check("pass:bots/technology.apoapsis/key_id") is None
    assert apoapsis.check("pass:bots/shared/sonatype/token") is None
    assert apoapsis.check("vault:eclipse-apoapsis/token") is None
    assert other.check("pass:bots/shared/sonatype/token") is not None


def test_the_references_of_an_organization_alone_enable_an_enforced_policy(tmp_path):
    config = _config(tmp_path, None, _organization({"allowed_references": {"pass": ["bots/{org_name}/**"]}}))

    policy = config.get_secret_access_policy(config.get_organization_config(_GITHUB_ID))

    assert policy is not None and policy.is_enforced
    assert policy.check("pass:bots/technology.other/key_id") is not None


def test_the_policy_applies_to_organization_configurations_of_the_webapp(tmp_path):
    """The WebApp builds the configuration of an organization from its installation, not from otterdog.json."""
    config = _config(
        tmp_path,
        {"allowed_references": {"pass": ["bots/{org_name}/**"]}},
        _organization({"allowed_references": {"pass": ["bots/shared/sonatype/**"]}}),
    )
    org_config = OrganizationConfig.of(
        _ORG_NAME, _GITHUB_ID, ".otterdog", "template", {"provider": "inmemory"}, str(tmp_path), str(tmp_path)
    )

    policy = config.get_secret_access_policy(org_config)

    assert policy is not None
    assert policy.check("pass:bots/technology.apoapsis/key_id") is None
    assert policy.check("pass:bots/shared/sonatype/token") is None
    assert policy.check("pass:bots/technology.other/key_id") is not None


@pytest.mark.parametrize(
    ("defaults_secrets", "organization_secrets", "error"),
    [
        ({"mode": "audit"}, None, "defaults.secrets.mode"),
        ({"allowed": {}}, None, "unexpected keys"),
        ({"allowed_references": {"pass": ["bots/{org}/**"]}}, None, "unknown placeholder"),
        (None, {"mode": "warn"}, "unexpected keys"),
        (None, {"allowed_references": {"pass": ["bots/{org}/**"]}}, "unknown placeholder"),
        ("enforce", None, "expected an object"),
    ],
)
def test_invalid_configurations_are_rejected(tmp_path, defaults_secrets, organization_secrets, error: str):
    with pytest.raises((RuntimeError, TypeError), match=re.escape(error)):
        _config(tmp_path, defaults_secrets, _organization(organization_secrets))


@pytest.fixture
def pass_provider(monkeypatch):
    provider = MagicMock()
    provider.get_secret.side_effect = lambda reference: f"secret of {reference}"
    monkeypatch.setattr(
        "otterdog.config.CredentialProvider.create",
        lambda provider_type, _defaults: provider if provider_type == "pass" else None,
    )
    return provider


def _resolver(tmp_path, mode: str) -> CredentialResolver:
    config = _config(tmp_path, {"mode": mode, "allowed_references": {"pass": ["bots/{org_name}/**"]}})
    return CredentialResolver(config).for_organization(config.get_organization_config(_GITHUB_ID))


def test_an_allowed_secret_is_resolved(tmp_path, pass_provider):
    resolver = _resolver(tmp_path, "enforce")

    assert resolver.get_secret("pass:bots/technology.apoapsis/key_id") == "secret of bots/technology.apoapsis/key_id"


def test_a_denied_secret_is_never_read_from_the_provider(tmp_path, pass_provider):
    resolver = _resolver(tmp_path, "enforce")

    with pytest.raises(
        RuntimeError, match=re.escape("organization 'technology.apoapsis' is not allowed to reference secret")
    ):
        resolver.get_secret("pass:bots/technology.other/key_id")

    pass_provider.get_secret.assert_not_called()


def test_a_denied_secret_is_resolved_with_a_warning_in_warn_mode(tmp_path, pass_provider, monkeypatch):
    warnings: list[str] = []
    monkeypatch.setattr("otterdog.config.print_warn", warnings.append)
    resolver = _resolver(tmp_path, "warn")

    assert resolver.get_secret("pass:bots/technology.other/key_id") == "secret of bots/technology.other/key_id"
    assert len(warnings) == 1 and "'pass:bots/technology.other/key_id'" in warnings[0]


def test_the_resolvers_of_organizations_share_the_credential_providers(tmp_path, pass_provider, monkeypatch):
    created: list[str] = []
    monkeypatch.setattr(
        "otterdog.config.CredentialProvider.create",
        lambda provider_type, _defaults: created.append(provider_type) or pass_provider,
    )
    config = _config(
        tmp_path,
        {"allowed_references": {"pass": ["bots/{org_name}/**"]}},
        _organization(),
        _organization(name="technology.other", github_id="eclipse-other"),
    )
    resolver = CredentialResolver(config)

    resolver.for_organization(config.get_organization_config(_GITHUB_ID)).get_secret("pass:bots/technology.apoapsis/a")
    resolver.for_organization(config.get_organization_config("eclipse-other")).get_secret(
        "pass:bots/technology.other/a"
    )

    assert created == ["pass"]


def _validation_context(policy: SecretAccessPolicy | None) -> ValidationContext:
    return ValidationContext(
        root_object=None,
        secret_resolver=CredentialResolver(MagicMock(spec=OtterdogConfig)),
        template_dir="",
        org_members=set(),
        default_team_names=set(),
        exclude_teams_pattern=None,
        secret_access_policy=policy,
    )


def _secret(value: str) -> RepositorySecret:
    return RepositorySecret(name="SECRET", value=value)


def _webhook(secret: str) -> OrganizationWebhook:
    return OrganizationWebhook.from_model_data(
        {
            "url": "https://example.org/hook",
            "events": ["push"],
            "active": True,
            "content_type": "json",
            "insecure_ssl": "0",
            "secret": secret,
        }
    )


def _secret_access_failures(context: ValidationContext) -> list[tuple[FailureType, str]]:
    return [(t, m) for t, m in context.validation_failures if "not allowed to use" in m]


@pytest.mark.parametrize(
    ("mode", "failure_type"),
    [(SecretAccessMode.ENFORCE, FailureType.ERROR), (SecretAccessMode.WARN, FailureType.WARNING)],
)
@pytest.mark.parametrize("model", [_secret, _webhook])
def test_validation_reports_denied_secrets(model, mode: SecretAccessMode, failure_type: FailureType):
    context = _validation_context(_policy(mode=mode))

    model("pass:bots/technology.other/key_id").validate(context, None)

    failures = _secret_access_failures(context)
    assert len(failures) == 1
    assert failures[0][0] == failure_type
    assert "'pass:bots/technology.other/key_id'" in failures[0][1]


@pytest.mark.parametrize("model", [_secret, _webhook])
@pytest.mark.parametrize("policy", [_policy(), None])
def test_validation_accepts_allowed_secrets(model, policy: SecretAccessPolicy | None):
    context = _validation_context(policy)

    model("pass:bots/technology.apoapsis/key_id").validate(context, None)

    assert _secret_access_failures(context) == []


@pytest.mark.parametrize("model", [_secret, _webhook])
def test_validation_ignores_dummy_secrets(model):
    context = _validation_context(_policy())

    model("********").validate(context, None)

    assert _secret_access_failures(context) == []
