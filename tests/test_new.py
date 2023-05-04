#  *******************************************************************************
#  Copyright (c) 2023 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the MIT License
#  which is available at https://spdx.org/licenses/MIT.html
#  SPDX-License-Identifier: MIT
#  *******************************************************************************
import dataclasses
import json
from dataclasses import dataclass, field, fields, Field
from typing import Union, Any, Protocol
from jsonbender import bend, K, S, OptionalS, Forall

from otterdog.models import ModelObject, UNSET
from otterdog.models.github_organization import GitHubOrganization
from otterdog.models.organization_webhook import OrganizationWebhook

team1_input = """
{
  "id": 1,
  "node_id": "MDQ6VGVhbTE=",
  "url": "https://api.github.com/teams/1",
  "html_url": "https://github.com/orgs/github/teams/justice-league",
  "name": "Justice League",
  "slug": "justice-league",
  "description": "A great team.",
  "privacy": "closed",
  "notification_setting": "notifications_enabled",
  "permission": "admin",
  "members_url": "https://api.github.com/teams/1/members{/member}",
  "repositories_url": "https://api.github.com/teams/1/repos",
  "parent": null,
  "members_count": 3,
  "repos_count": 10,
  "created_at": "2017-07-14T16:53:42Z",
  "updated_at": "2017-08-17T12:37:15Z",
  "organization": {
    "login": "github",
    "id": 1,
    "node_id": "MDEyOk9yZ2FuaXphdGlvbjE=",
    "url": "https://api.github.com/orgs/github",
    "repos_url": "https://api.github.com/orgs/github/repos",
    "events_url": "https://api.github.com/orgs/github/events",
    "hooks_url": "https://api.github.com/orgs/github/hooks",
    "issues_url": "https://api.github.com/orgs/github/issues",
    "members_url": "https://api.github.com/orgs/github/members{/member}",
    "public_members_url": "https://api.github.com/orgs/github/public_members{/member}",
    "avatar_url": "https://github.com/images/error/octocat_happy.gif",
    "description": "A great organization",
    "name": "github",
    "company": "GitHub",
    "blog": "https://github.com/blog",
    "location": "San Francisco",
    "email": "octocat@github.com",
    "is_verified": true,
    "has_organization_projects": true,
    "has_repository_projects": true,
    "public_repos": 2,
    "public_gists": 1,
    "followers": 20,
    "following": 0,
    "html_url": "https://github.com/octocat",
    "created_at": "2008-01-14T04:33:35Z",
    "updated_at": "2017-08-17T12:37:15Z",
    "type": "Organization"
  }
}
"""

team2_input = """
{
  "id": 2,
  "node_id": "MDQ6VGVhbCE=",
  "url": "https://api.github.com/teams/2",
  "html_url": "https://github.com/orgs/github/teams/captain-marvel",
  "name": "Captain Mavel",
  "slug": "captain-marvel",
  "description": "A great team.",
  "privacy": "closed",
  "notification_setting": "notifications_enabled",
  "permission": "admin",
  "members_url": "https://api.github.com/teams/2/members{/member}",
  "repositories_url": "https://api.github.com/teams/1/repos",
  "parent": null,
  "members_count": 3,
  "repos_count": 10,
  "created_at": "2017-07-14T16:53:42Z",
  "updated_at": "2017-08-17T12:37:15Z",
  "organization": {
    "login": "github",
    "id": 1,
    "node_id": "MDEyOk9yZ2FuaXphdGlvbjE=",
    "url": "https://api.github.com/orgs/github",
    "repos_url": "https://api.github.com/orgs/github/repos",
    "events_url": "https://api.github.com/orgs/github/events",
    "hooks_url": "https://api.github.com/orgs/github/hooks",
    "issues_url": "https://api.github.com/orgs/github/issues",
    "members_url": "https://api.github.com/orgs/github/members{/member}",
    "public_members_url": "https://api.github.com/orgs/github/public_members{/member}",
    "avatar_url": "https://github.com/images/error/octocat_happy.gif",
    "description": "A great organization",
    "name": "github",
    "company": "GitHub",
    "blog": "https://github.com/blog",
    "location": "San Francisco",
    "email": "octocat@github.com",
    "is_verified": true,
    "has_organization_projects": true,
    "has_repository_projects": true,
    "public_repos": 2,
    "public_gists": 1,
    "followers": 20,
    "following": 0,
    "html_url": "https://github.com/octocat",
    "created_at": "2008-01-14T04:33:35Z",
    "updated_at": "2017-08-17T12:37:15Z",
    "type": "Organization"
  }
}
"""

test_webhook1 = """
{
  "id": 1,
  "url": "https://api.github.com/orgs/octocat/hooks/1",
  "ping_url": "https://api.github.com/orgs/octocat/hooks/1/pings",
  "deliveries_url": "https://api.github.com/orgs/octocat/hooks/1/deliveries",
  "name": "web",
  "events": [
    "push",
    "pull_request"
  ],
  "active": true,
  "config": {
    "url": "http://example.com",
    "content_type": "json",
    "insecure_ssl": "0"
  },
  "updated_at": "2011-09-06T20:39:23Z",
  "created_at": "2011-09-06T17:26:27Z",
  "type": "Organization"
}
"""

@dataclass
class ModelObject1(Protocol):
    def _get_model_fields(self) -> list[Field]:
        return [f for f in fields(self) if f.metadata.get("external_only", False) is False]


@dataclass
class Team(ModelObject1):
    node_id: str = field(metadata={"external_only": True})
    name: str
    slug: str
    description: str
    organization_login: str
    privacy: str
    notification_setting: str
    permission: str
    parent_team: int

    def test(self):
        for f in fields(self):
            print(f"{f.name}={getattr(self, f.name)}")

    def diff(self, other: "Team") -> bool:
        for f in self._get_model_fields():
            print(f"{f.name}={getattr(self, f.name)}")
        return True

    @classmethod
    def from_github_model(cls, data: dict[str, Any]):
        mapping = {
            "node_id": S("node_id"),
            "name": S("name"),
            "slug": S("slug"),
            "description": S("description"),
            "organization_login": S("organization", "login"),
            "privacy": S("privacy"),
            "notification_setting": S("notification_setting"),
            "permission": S("permission"),
            "parent_team": S("parent")
        }

        mapped_dict = bend(mapping, data)
        return cls(**mapped_dict)


def test_full(otterdogtest_json):
    org = GitHubOrganization.from_model(otterdogtest_json)
    print(org)


def test():
    webhook = OrganizationWebhook.from_provider(json.loads(test_webhook1))
    print(webhook)
    # team1 = Team.from_github_model(json.loads(team1_input))
    # team2 = Team.from_github_model(json.loads(team2_input))
    #
    # team1.test()
    # print()
    # team2.test()
    #
    # print()
    # team1.diff(team2)

# def test():
#     file = f"../orgs/test.json"
#
#     with open(file) as f:
#         json = f.read()
#
#         definition = jsons.loads(json, OrganizationDefinition)
#         print(definition)
#         print(definition.content.to_dict())
#
#
# @dataclass
# class ResourceDefinition:
#     provider: str
#     resource: str
#     content: dict[str, str]
#
#
# @dataclass(init=False)
# class OrganizationSettings:
#     name: str = None
#     plan: str = None
#     billing_email: str = None
#     company: str = None
#     email: str = None
#     twitter_username: str = None
#     location: str = None
#     description: str = None
#     blog: str = None
#
#     has_organization_projects: bool = None
#     has_repository_projects: bool = None
#
#     default_repository_permission: str = None
#
#     members_can_create_private_repositories: bool = None
#     members_can_create_public_repositories: bool = None
#
#     members_can_fork_private_repositories: bool = None
#
#     web_commit_signoff_required: bool = None
#
#     dependabot_alerts_enabled_for_new_repositories: bool = None
#     dependabot_security_updates_enabled_for_new_repositories: bool = None
#     dependency_graph_enabled_for_new_repositories: bool = None
#
#     def to_dict(self):
#         result = {}
#
#         for field in fields(self):
#             result[field.name] = getattr(self, field.name)
#
#         # for attribute in dir(self):
#         #     print(attribute, getattr(self, attribute))
#
#         # for attr, value in vars(self).items():
#         #     result[attr] = value
#         # for attr, value in self.__dict__.items():
#         #     result[attr] = value
#
#         return result
#
# @dataclass
# class OrganizationDefinition(ResourceDefinition):
#     provider: str
#     resource: str
#     content: OrganizationSettings
