import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from jsonbender import bend
from pretend import stub

from otterdog.models.github_organization import GitHubOrganization, _process_single_repo
from otterdog.models.organization_ruleset import OrganizationRuleset
from otterdog.models.repo_ruleset import RepositoryRuleset


def ruleset_data(*actors):
    return {
        "id": 1,
        "name": "protected-branches",
        "enforcement": "active",
        "target": "branch",
        "conditions": {
            "ref_name": {"include": ["refs/heads/main"], "exclude": []},
            "repository_name": {"include": ["~ALL"], "exclude": [], "protected": False},
        },
        "bypass_actors": list(actors),
        "rules": [],
    }


def user_actor(user_id=123, bypass_mode="always"):
    return {"actor_type": "User", "actor_id": user_id, "bypass_mode": bypass_mode}


def minimal_config(**overrides):
    values = {
        "default_org_config": {"settings": {}},
        "default_org_ruleset_config": {},
        "default_repo_ruleset_config": None,
        "default_org_role_config": None,
        "default_team_config": None,
        "default_repo_config": None,
        "default_org_webhook_config": None,
        "default_org_secret_config": None,
        "default_org_dependabot_secret_config": None,
        "default_org_codespaces_secret_config": None,
        "default_org_variable_config": None,
        "default_branch_protection_rule_config": None,
        "default_repo_secret_config": None,
        "default_repo_dependabot_secret_config": None,
        "default_repo_codespaces_secret_config": None,
        "default_repo_variable_config": None,
        "default_repo_webhook_config": None,
        "default_environment_config": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def organization_provider(rulesets):
    settings = AsyncMock(return_value={})
    provider = stub(
        rest_api=stub(org=stub(get_app_installations=AsyncMock(return_value=[]))),
        get_org_settings=settings,
        get_org_workflow_settings=AsyncMock(return_value={}),
        get_org_rulesets=AsyncMock(return_value=rulesets),
        get_user_logins=AsyncMock(return_value={123: "alice"}),
    )
    return provider


@pytest.mark.asyncio
async def test_organization_loader_enriches_users_before_conversion():
    rulesets = [ruleset_data(user_actor(123, "pull_request"))]
    provider = organization_provider(rulesets)

    with patch("otterdog.models.github_organization.OrganizationSettings.from_provider_data") as settings_model:
        settings_model.return_value = SimpleNamespace(plan="enterprise")
        organization = await GitHubOrganization.load_from_provider("project", "acme", minimal_config(), provider)

    provider.get_user_logins.assert_awaited_once_with({123})
    assert organization.rulesets[0].bypass_actors == ["@alice:pull_request"]
    assert rulesets[0]["bypass_actors"][0]["user_login"] == "alice"


@pytest.mark.asyncio
async def test_organization_loader_deduplicates_ids_and_skips_lookup_without_users():
    rulesets = [ruleset_data(user_actor(123)), ruleset_data(user_actor(123))]
    provider = organization_provider(rulesets)
    with patch("otterdog.models.github_organization.OrganizationSettings.from_provider_data") as settings_model:
        settings_model.return_value = SimpleNamespace(plan="enterprise")
        await GitHubOrganization.load_from_provider("project", "acme", minimal_config(), provider)
    provider.get_user_logins.assert_awaited_once_with({123})

    provider = organization_provider([ruleset_data({"actor_type": "Team", "actor_id": 2})])
    with patch("otterdog.models.github_organization.OrganizationSettings.from_provider_data") as settings_model:
        settings_model.return_value = SimpleNamespace(plan="enterprise")
        await GitHubOrganization.load_from_provider("project", "acme", minimal_config(), provider)
    provider.get_user_logins.assert_not_awaited()


@pytest.mark.asyncio
async def test_organization_loader_skips_unresolved_user_actor():
    rulesets = [ruleset_data(user_actor())]
    provider = organization_provider(rulesets)
    provider.get_user_logins.return_value = {}

    with patch("otterdog.models.github_organization.OrganizationSettings.from_provider_data") as settings_model:
        settings_model.return_value = SimpleNamespace(plan="enterprise")
        organization = await GitHubOrganization.load_from_provider("project", "acme", minimal_config(), provider)

    assert "user_login" not in rulesets[0]["bypass_actors"][0]
    assert organization.rulesets[0].bypass_actors == []


def repository_provider(rulesets):
    repo_data = {"id": 1, "node_id": "repo-node", "name": "backend", "private": False}
    repository = stub(
        add_ruleset=lambda rule: repository.rulesets.append(rule),
        rulesets=[],
        unset_team_permissions=lambda: None,
        set_team_permissions=lambda permissions: None,
    )
    rest_repo = stub(
        get_repo_data=AsyncMock(return_value=repo_data),
        get_workflow_settings=AsyncMock(return_value={}),
        get_rulesets=AsyncMock(return_value=rulesets),
    )
    provider = stub(
        rest_api=stub(repo=rest_repo),
        get_user_logins=AsyncMock(return_value={123: "alice"}),
    )
    return provider, repository


@pytest.mark.asyncio
async def test_repository_loader_enriches_user_before_conversion():
    rulesets = [ruleset_data(user_actor(123, "pull_request"))]
    provider, repository = repository_provider(rulesets)
    config = minimal_config(default_repo_ruleset_config={})

    with patch("otterdog.models.github_organization.Repository.from_provider_data", return_value=repository):
        result = await _process_single_repo(provider, "acme", "backend", config, {}, None, {})

    assert result[1].rulesets[0].bypass_actors == ["@alice:pull_request"]
    provider.get_user_logins.assert_awaited_once_with({123})


@pytest.mark.asyncio
async def test_repository_loader_skips_lookup_without_users_and_skips_unresolved_user():
    rulesets = [ruleset_data({"actor_type": "Team", "actor_id": 2, "team_slug": "acme/backend"})]
    provider, repository = repository_provider(rulesets)
    config = minimal_config(default_repo_ruleset_config={})
    with patch("otterdog.models.github_organization.Repository.from_provider_data", return_value=repository):
        await _process_single_repo(provider, "acme", "backend", config, {}, {}, {})
    provider.get_user_logins.assert_not_awaited()

    provider, repository = repository_provider([ruleset_data(user_actor())])
    provider.get_user_logins.return_value = {}
    with patch("otterdog.models.github_organization.Repository.from_provider_data", return_value=repository):
        result = await _process_single_repo(provider, "acme", "backend", config, {}, {}, {})
    assert result[1].rulesets[0].bypass_actors == []


@pytest.mark.asyncio
async def test_repeated_repository_loads_reuse_provider_user_cache():
    from otterdog.providers.github import GitHubProvider

    rulesets = [ruleset_data(user_actor())]
    provider_stub, repository = repository_provider(rulesets)
    user_lookup = AsyncMock(return_value="alice")
    provider = GitHubProvider(None)
    provider.rest_api = stub(repo=provider_stub.rest_api.repo, user=stub(get_user_login=user_lookup))
    config = minimal_config(default_repo_ruleset_config={})
    with patch("otterdog.models.github_organization.Repository.from_provider_data", return_value=repository):
        await _process_single_repo(provider, "acme", "backend", config, {}, {}, {})
        await _process_single_repo(provider, "acme", "backend", config, {}, {}, {})
    user_lookup.assert_awaited_once_with(123)


@pytest.mark.asyncio
async def test_repository_loader_deduplicates_repeated_user_actor_ids():
    rulesets = [ruleset_data(user_actor(), user_actor())]
    provider, repository = repository_provider(rulesets)
    config = minimal_config(default_repo_ruleset_config={})
    with patch("otterdog.models.github_organization.Repository.from_provider_data", return_value=repository):
        await _process_single_repo(provider, "acme", "backend", config, {}, {}, {})
    provider.get_user_logins.assert_awaited_once_with({123})


@pytest.mark.asyncio
async def test_provider_user_login_cache_and_partial_failure():
    from otterdog.providers.github import GitHubProvider

    calls = []
    responses = {123: "alice", 456: "bob"}

    async def get_user_login(user_id):
        calls.append(user_id)
        return responses[user_id]

    provider = GitHubProvider(None)
    provider.rest_api = stub(user=stub(get_user_login=get_user_login))
    assert await provider.get_user_logins({123}) == {123: "alice"}
    assert await provider.get_user_logins({123}) == {123: "alice"}
    assert await provider.get_user_logins({123, 456}) == {123: "alice", 456: "bob"}
    assert calls == [123, 456]

    responses[789] = RuntimeError("failed")

    async def failing_login(user_id):
        calls.append(user_id)
        response = responses[user_id]
        if isinstance(response, Exception):
            raise response
        return response

    provider.rest_api.user.get_user_login = failing_login
    assert await provider.get_user_logins({789}) == {}
    responses[789] = "carol"
    assert await provider.get_user_logins({123, 789}) == {123: "alice", 789: "carol"}
    assert calls == [123, 456, 789, 789]


@pytest.mark.asyncio
async def test_provider_partial_population_keeps_successful_id_cached():
    from otterdog.providers.github import GitHubProvider

    calls = []
    attempts = {456: 0}

    async def get_user_login(user_id):
        calls.append(user_id)
        if user_id == 456:
            attempts[456] += 1
            if attempts[456] == 1:
                raise RuntimeError("failed")
        return {123: "alice", 456: "bob"}[user_id]

    provider = GitHubProvider(None)
    provider.rest_api = stub(user=stub(get_user_login=get_user_login))
    assert await provider.get_user_logins({123}) == {123: "alice"}
    assert await provider.get_user_logins({123, 456}) == {123: "alice"}
    assert await provider.get_user_logins({123}) == {123: "alice"}
    assert await provider.get_user_logins({456}) == {456: "bob"}
    assert calls == [123, 456, 456]
    assert attempts[456] == 2


@pytest.mark.asyncio
async def test_provider_concurrent_overlapping_lookups_fetch_each_id_once():
    from otterdog.providers.github import GitHubProvider

    started = asyncio.Event()
    release = asyncio.Event()
    calls = []

    async def get_user_login(user_id):
        calls.append(user_id)
        if user_id == 123:
            started.set()
            await release.wait()
        return {123: "alice", 456: "bob"}[user_id]

    provider = GitHubProvider(None)
    provider.rest_api = stub(user=stub(get_user_login=get_user_login))
    first = asyncio.create_task(provider.get_user_logins({123}))
    await started.wait()
    second = asyncio.create_task(provider.get_user_logins({123, 456}))
    await asyncio.sleep(0)
    assert calls == [123]
    release.set()
    assert await first == {123: "alice"}
    assert await second == {123: "alice", 456: "bob"}
    assert sorted(calls) == [123, 456]


@pytest.mark.asyncio
async def test_ruleset_actor_round_trip_preserves_user_and_bypass_mode():
    from otterdog.models.ruleset import Ruleset

    provider = stub(rest_api=stub(user=stub(get_user_ids=AsyncMock(return_value=(123, "node")))))
    for configured in ("@alice", "@alice:pull_request"):
        mapping = await Ruleset.get_mapping_to_provider("acme", {"bypass_actors": [configured]}, provider)
        provider_data = bend(mapping, {"bypass_actors": [configured]})
        response = ruleset_data(provider_data["bypass_actors"][0])
        actor = response["bypass_actors"][0]
        actor["user_login"] = "alice"
        assert RepositoryRuleset.from_provider_data("acme", response).bypass_actors == [configured]
        assert OrganizationRuleset.from_provider_data("acme", response).bypass_actors == [configured]
