#  *******************************************************************************
#  Copyright (c) 2023-2025 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

import dataclasses
import json
import os
import re
from abc import abstractmethod
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

from rich.markup import escape

from otterdog.credentials import SECRET_PROVIDER_TYPES, CredentialPlaceHolders, CredentialProvider
from otterdog.credentials.secret_access_policy import SecretAccessMode, SecretAccessPolicy
from otterdog.models import CostPolicy

from .jsonnet import JsonnetConfig
from .logging import get_logger, print_warn
from .utils import ExclusionPatterns, deep_merge_dict, is_local_template, jsonnet_evaluate_file, query_json

if TYPE_CHECKING:
    from collections.abc import Mapping

    from otterdog.credentials import Credentials

_logger = get_logger(__name__)


def load_json_or_jsonnet(file: Path) -> dict[str, Any]:
    """Load JSON (.json) or JSONNET (.jsonnet) and return its content as a dictionary."""

    if file.suffix == ".jsonnet":
        data = jsonnet_evaluate_file(str(file))
    else:
        try:
            data = json.loads(file.read_text())
        except json.JSONDecodeError as e:
            raise RuntimeError(f"failed to parse json file '{file}': {e}") from e
    if not isinstance(data, dict):
        raise TypeError(f"expected JSON object in file '{file}', got: {type(data)}")
    return data


class OrganizationConfig:
    def __init__(
        self,
        name: str,
        github_id: str,
        config_repo: str,
        base_template: str,
        jsonnet_config: JsonnetConfig,
        credential_data: dict[str, Any],
        approval_teams: str | None = None,
        admin_teams: str | None = None,
        allowed_secret_references: Mapping[str, tuple[str, ...]] | None = None,
    ):
        self._name = name
        self._github_id = github_id
        self._config_repo = config_repo
        self._base_template = base_template
        self._jsonnet_config = jsonnet_config
        self._credential_data = credential_data
        self._approval_teams = approval_teams
        self._admin_teams = admin_teams
        self._allowed_secret_references = allowed_secret_references

    @property
    def name(self):
        return self._name

    @property
    def github_id(self) -> str:
        return self._github_id

    @property
    def config_repo(self) -> str:
        return self._config_repo

    @property
    def base_template(self) -> str:
        return self._base_template

    @property
    def jsonnet_config(self) -> JsonnetConfig:
        return self._jsonnet_config

    @property
    def approval_teams(self) -> str | None:
        return self._approval_teams

    @property
    def admin_teams(self) -> str | None:
        return self._admin_teams

    @property
    def credential_data(self) -> dict[str, Any]:
        return self._credential_data

    @credential_data.setter
    def credential_data(self, data: dict[str, Any]) -> None:
        self._credential_data = data

    @property
    def allowed_secret_references(self) -> Mapping[str, tuple[str, ...]] | None:
        """The references to secrets allowed for this organization, in addition to the default ones, if configured."""
        return self._allowed_secret_references

    def __repr__(self) -> str:
        return (
            f"OrganizationConfig('{self.name}', '{self.github_id}', "
            f"'{self.config_repo}', {json.dumps(self.credential_data)})"
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any], otterdog_config: OtterdogConfig) -> OrganizationConfig:
        name = data.get("name")
        if name is None:
            raise RuntimeError(f"missing required name for organization config with data: '{json.dumps(data)}'")

        github_id = data.get("github_id")
        if github_id is None:
            raise RuntimeError(f"missing required github_id for organization config with name '{name}'")

        config_repo = data.get("config_repo", otterdog_config.default_config_repo)
        base_template = data.get("base_template", otterdog_config.default_base_template)
        if is_local_template(base_template):
            # a relative path of a local base template is relative to the directory of the otterdog configuration
            base_template = os.path.join(otterdog_config.working_dir, os.path.expanduser(base_template))

        approval_teams = cls._normalize_team_list(data.get("approval_teams"), "approval_teams", name)
        admin_teams = cls._normalize_team_list(data.get("admin_teams"), "admin_teams", name)

        jsonnet_config = JsonnetConfig(
            github_id,
            otterdog_config.jsonnet_base_dir,
            base_template,
            otterdog_config.local_mode,
        )

        credentials = data.get("credentials", {})
        if credentials is None:
            raise RuntimeError(f"missing required credentials for organization config with name '{name}'")

        allowed_secret_references = cls._parse_allowed_secret_references(data.get("secrets"), name)

        return cls(
            name,
            github_id,
            config_repo,
            base_template,
            jsonnet_config,
            credentials,
            approval_teams,
            admin_teams,
            allowed_secret_references,
        )

    @staticmethod
    def _parse_allowed_secret_references(value: Any, org_name: str) -> dict[str, tuple[str, ...]] | None:
        if value is None:
            return None

        key = f"organizations[{org_name}].secrets"
        if not isinstance(value, dict):
            raise TypeError(f"invalid '{key}': expected an object, got {value!r}")
        # the mode is global, see 'defaults.secrets.mode'
        unknown_keys = set(value.keys()) - {"allowed_references"}
        if unknown_keys:
            raise RuntimeError(f"invalid '{key}': unexpected keys {sorted(unknown_keys)}")

        return SecretAccessPolicy.parse_allowed_references(value.get("allowed_references"), f"{key}.allowed_references")

    @staticmethod
    def _normalize_team_list(value: Any, key: str, org_name: str) -> str | None:
        """Accepts either a plain string ("project-leads$") or a list of strings
        (["test-team", "project-leads", ".*-committers$"]) for a comma-separated
        team-pattern config entry and normalizes it to a single comma-joined string."""
        if value is None or isinstance(value, str):
            return value
        elif isinstance(value, list):
            return ",".join(str(entry) for entry in value)
        else:
            raise RuntimeError(
                f"invalid '{key}' for organization config with name '{org_name}': "
                f"expected a string or a list of strings, got {type(value)}"
            )

    @classmethod
    def of(
        cls,
        project_name: str,
        github_id: str,
        config_repo: str,
        base_template: str,
        credential_data: dict[str, Any],
        base_dir: str,
        work_dir: str,
    ) -> OrganizationConfig:
        jsonnet_config = JsonnetConfig(
            github_id,
            base_dir,
            base_template,
            False,
            work_dir,
        )

        return cls(project_name, github_id, config_repo, base_template, jsonnet_config, credential_data)


class SecretResolver(Protocol):
    @abstractmethod
    def is_supported_secret_provider(self, provider_type: str) -> bool: ...

    @abstractmethod
    def get_secret(self, data: str) -> str: ...


class CredentialResolver(SecretResolver):
    def __init__(self, config: OtterdogConfig) -> None:
        self._config = config
        self._credential_providers: dict[str, CredentialProvider] = {}
        self._org_name: str | None = None
        self._secret_access_policy: SecretAccessPolicy | None = None

    def for_organization(self, org_config: OrganizationConfig) -> CredentialResolver:
        """
        Returns a resolver of the secrets referenced by the configuration of the given organization, which enforces
        its secret access policy, if any. It shares the credential providers of this resolver.
        """
        resolver = CredentialResolver(self._config)
        resolver._credential_providers = self._credential_providers
        resolver._org_name = org_config.name
        resolver._secret_access_policy = self._config.get_secret_access_policy(org_config)
        return resolver

    def _get_credential_provider(self, provider_type: str) -> CredentialProvider | None:
        provider = self._credential_providers.get(provider_type)
        if provider is None:
            provider = CredentialProvider.create(
                provider_type, query_json(f"defaults.{provider_type}", self._config.configuration) or {}
            )
            if provider is not None:
                self._credential_providers[provider_type] = provider

        return provider

    def get_credentials(self, org_config: OrganizationConfig, only_token: bool = False) -> Credentials:
        provider_type = org_config.credential_data.get("provider")

        if provider_type is None:
            provider_type = self._config.default_credential_provider

        if not provider_type:
            raise RuntimeError(f"no credential provider configured for organization '{org_config.name}'")

        provider = self._get_credential_provider(provider_type)
        if provider is not None:
            # Centrally managed placeholders for credential data provided within the default section.
            # This way all providers can support the same set of placeholders.
            placeholders = CredentialPlaceHolders(org_name=org_config.name, github_id=org_config.github_id)
            return provider.get_credentials(placeholders, org_config.credential_data, only_token)
        else:
            raise RuntimeError(f"unsupported credential provider '{provider_type}'")

    def is_supported_secret_provider(self, provider_type: str) -> bool:
        return provider_type in SECRET_PROVIDER_TYPES

    def get_secret(self, secret_data: str) -> str:
        self._check_secret_access(secret_data)

        if secret_data and ":" in secret_data:
            # the data of the provider can contain ':'
            provider_type, data = re.split(":", secret_data, maxsplit=1)
            provider = self._get_credential_provider(provider_type)
            if provider is not None:
                return provider.get_secret(data)
            else:
                return secret_data
        else:
            return secret_data

    def _check_secret_access(self, secret_data: str) -> None:
        policy = self._secret_access_policy
        if policy is None or not secret_data:
            return

        violation = policy.check(secret_data)
        if violation is None:
            return

        message = f"organization '{self._org_name}' is not allowed to reference secret '{secret_data}': {violation}"
        if policy.is_enforced:
            raise RuntimeError(message)
        else:
            # the reference comes from the configuration, it must not be read as markup
            print_warn(escape(message))


@dataclasses.dataclass(frozen=True)
class OtterdogConfig:
    configuration: Mapping[str, Any]
    local_mode: bool
    working_dir: str

    _base_url: str = dataclasses.field(init=False)
    _jsonnet_config: Mapping[str, Any] = dataclasses.field(init=False)
    _github_config: Mapping[str, Any] = dataclasses.field(init=False)
    _default_credential_provider: str = dataclasses.field(init=False)
    _jsonnet_base_dir: str = dataclasses.field(init=False)
    # None if 'defaults.secrets' is not configured
    _secret_access_mode: SecretAccessMode | None = dataclasses.field(init=False)
    _default_allowed_secret_references: Mapping[str, tuple[str, ...]] = dataclasses.field(init=False)

    _organizations_map: dict[str, OrganizationConfig] = dataclasses.field(init=False, default_factory=dict)
    # unlike _organizations_map, never overwritten by an organization whose name is the github_id of another one
    _organizations_by_github_id: dict[str, OrganizationConfig] = dataclasses.field(init=False, default_factory=dict)
    _organizations: list[OrganizationConfig] = dataclasses.field(init=False, default_factory=list)

    def __post_init__(self):
        object.__setattr__(self, "_base_url", query_json("defaults.base_url", self.configuration) or None)
        object.__setattr__(self, "_jsonnet_config", query_json("defaults.jsonnet", self.configuration) or {})
        object.__setattr__(self, "_github_config", query_json("defaults.github", self.configuration) or {})
        object.__setattr__(
            self, "_default_credential_provider", query_json("defaults.credentials.provider", self.configuration) or ""
        )

        self._init_secret_access_defaults()

        object.__setattr__(
            self,
            "_jsonnet_base_dir",
            os.path.join(self.working_dir, self._jsonnet_config.get("config_dir", "orgs")),
        )
        if not os.path.exists(self._jsonnet_base_dir):
            os.makedirs(self._jsonnet_base_dir)

        organizations = self.configuration.get("organizations", [])
        for org in (o for o in organizations if not o.get("archived", False)):
            org_config = OrganizationConfig.from_dict(org, self)
            self._organizations.append(org_config)
            self._organizations_map[org_config.name.lower()] = org_config
            self._organizations_map[org_config.github_id.lower()] = org_config
            self._organizations_by_github_id[org_config.github_id.lower()] = org_config

    def _init_secret_access_defaults(self) -> None:
        secrets = query_json("defaults.secrets", self.configuration)
        if secrets is None:
            object.__setattr__(self, "_secret_access_mode", None)
            object.__setattr__(self, "_default_allowed_secret_references", {})
            return

        if not isinstance(secrets, dict):
            raise TypeError(f"invalid 'defaults.secrets': expected an object, got {secrets!r}")
        unknown_keys = set(secrets.keys()) - {"mode", "allowed_references"}
        if unknown_keys:
            raise RuntimeError(f"invalid 'defaults.secrets': unexpected keys {sorted(unknown_keys)}")

        object.__setattr__(
            self, "_secret_access_mode", SecretAccessPolicy.parse_mode(secrets.get("mode"), "defaults.secrets.mode")
        )
        object.__setattr__(
            self,
            "_default_allowed_secret_references",
            SecretAccessPolicy.parse_allowed_references(
                secrets.get("allowed_references"), "defaults.secrets.allowed_references"
            ),
        )

    def get_secret_access_policy(self, org_config: OrganizationConfig) -> SecretAccessPolicy | None:
        """
        Returns the policy restricting the secrets that the configuration of the given organization can reference,
        None if no policy is configured, neither in 'defaults.secrets' nor for the organization.

        The placeholders are replaced by the name and github_id of the given organization configuration, never by
        the ones of its jsonnet configuration, which may come from a pull request. The references allowed for the
        organization are looked up by its github_id, as the WebApp does not build its organization configurations
        from this configuration.
        """
        configured_org = self._organizations_by_github_id.get(org_config.github_id.lower())
        org_references = configured_org.allowed_secret_references if configured_org is not None else None

        if self._secret_access_mode is None and org_references is None:
            return None

        mode = self._secret_access_mode or SecretAccessMode.ENFORCE
        default_references = self._default_allowed_secret_references
        org_references = org_references or {}

        allowed_references = {
            provider_type: (*default_references.get(provider_type, ()), *org_references.get(provider_type, ()))
            for provider_type in {*default_references.keys(), *org_references.keys()}
        }

        placeholders = CredentialPlaceHolders(org_name=org_config.name, github_id=org_config.github_id)
        return SecretAccessPolicy(mode, allowed_references, placeholders)

    @property
    def base_url(self) -> str:
        return self._base_url

    @property
    def jsonnet_base_dir(self) -> str:
        return self._jsonnet_base_dir

    @property
    def default_config_repo(self) -> str:
        return self._github_config.get("config_repo", ".otterdog")

    @property
    def default_no_web_ui(self) -> bool:
        return bool(self._github_config.get("no_web_ui", False))

    @property
    def default_team_exclusions(self) -> list[str]:
        return self._github_config.get("exclude_teams", [])

    @cached_property
    def exclude_teams_pattern(self) -> ExclusionPatterns | None:
        team_exclusions = self.default_team_exclusions
        if len(team_exclusions) == 0:
            return None
        else:
            return ExclusionPatterns(team_exclusions)

    @property
    def default_environment_exclusions(self) -> list[str]:
        return self._github_config.get("exclude_environments", [])

    @cached_property
    def exclude_environments_pattern(self) -> ExclusionPatterns | None:
        environment_exclusions = self.default_environment_exclusions
        if len(environment_exclusions) == 0:
            return None
        else:
            return ExclusionPatterns(environment_exclusions)

    @property
    def default_credential_provider(self) -> str:
        return self._default_credential_provider

    @cached_property
    def cost_policy(self) -> CostPolicy:
        cost_policy_config = query_json("defaults.cost_policy", self.configuration)
        if cost_policy_config is None:
            cost_policy_config = {}
        elif not isinstance(cost_policy_config, dict):
            raise RuntimeError(f"'defaults.cost_policy' must be an object, got: {cost_policy_config!r}")
        free_max_cache_size_gb = cost_policy_config.get("free_max_cache_size_gb", CostPolicy.free_max_cache_size_gb)
        if (
            not isinstance(free_max_cache_size_gb, int)
            or isinstance(free_max_cache_size_gb, bool)
            or free_max_cache_size_gb < 0
        ):
            raise RuntimeError(
                "'defaults.cost_policy.free_max_cache_size_gb' must be a non-negative integer, "
                f"got: {free_max_cache_size_gb!r}"
            )
        return CostPolicy(free_max_cache_size_gb=free_max_cache_size_gb)

    @property
    def default_base_template(self) -> str:
        base_template = self._jsonnet_config.get("base_template")
        if base_template is None:
            raise RuntimeError(
                "need to define a base template in your otterdog config, key: 'defaults.jsonnet.base_template'"
            )
        return base_template

    def _get_organization_config(self, project_or_organization_name: str):
        return self._organizations_map.get(project_or_organization_name.lower())

    @property
    def project_names(self) -> list[str]:
        return [config.name for config in self._organizations]

    @property
    def organization_names(self) -> list[str]:
        return [config.github_id for config in self._organizations]

    def get_project_name(self, github_id: str) -> str | None:
        org_config = self._get_organization_config(github_id)
        if org_config is not None:
            return org_config.name
        else:
            return None

    def get_organization_config(self, project_or_organization_name: str) -> OrganizationConfig:
        org_config = self._get_organization_config(project_or_organization_name)
        if org_config is None:
            raise RuntimeError(f"unknown organization with name / github_id '{project_or_organization_name}'")
        return org_config

    @classmethod
    def from_file(cls, config_file: str, local_mode: bool, working_dir: str | None = None) -> OtterdogConfig:
        config_file_file = Path(config_file)
        if not config_file_file.exists():
            raise RuntimeError(f"configuration file '{config_file}' not found")

        config_file_dir = config_file_file.parent

        configuration = load_json_or_jsonnet(config_file_file)

        override_defaults_file = config_file_dir / ".otterdog-defaults.json"
        if override_defaults_file.exists():
            defaults = load_json_or_jsonnet(override_defaults_file)
            _logger.trace("loading default overrides from '%s'", override_defaults_file)
            configuration["defaults"] = deep_merge_dict(defaults, configuration.setdefault("defaults", {}))
        else:
            _logger.debug("no default overrides found at '%s'", override_defaults_file)

        return cls(configuration, local_mode, working_dir if working_dir is not None else str(config_file_dir))

    @classmethod
    def from_dict(cls, configuration: Mapping[str, Any], local_mode: bool, working_dir: str) -> OtterdogConfig:
        return cls(configuration, local_mode, working_dir)
