#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from odmantic import EmbeddedModel, Field, Model

from otterdog.webapp.utils import current_utc_time


class InstallationStatus(str, Enum):
    INSTALLED = "installed"
    NOT_INSTALLED = "not_installed"
    SUSPENDED = "suspended"

    def __str__(self) -> str:
        return self.name


class InstallationModel(Model):
    github_id: str = Field(primary_field=True)
    project_name: str | None = Field(unique=True, index=True)
    installation_id: int = Field(index=True, default=0)
    installation_status: InstallationStatus
    config_repo: str | None = None
    base_template: str | None = None


class TaskStatus(str, Enum):
    CREATED = "created"
    SCHEDULED = "scheduled"
    FINISHED = "finished"
    FAILED = "failed"

    def __str__(self) -> str:
        return self.name


class TaskModel(Model):
    type: str = Field(index=True)
    org_id: str = Field(index=True)
    repo_name: str = Field(index=True)
    pull_request: int = 0
    status: TaskStatus = TaskStatus.CREATED
    log: str | None = None
    cache_stats: str = ""
    rate_limit_remaining: str = ""
    created_at: datetime = Field(index=True, default_factory=current_utc_time)
    updated_at: datetime = Field(default_factory=current_utc_time)


class ConfigurationModel(Model):
    github_id: str = Field(primary_field=True)
    project_name: str | None = Field(unique=True, index=True)
    config: dict
    sha: str


class PullRequestStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"
    MERGED = "merged"

    def __str__(self) -> str:
        return self.name


class ApplyStatus(str, Enum):
    NOT_APPLIED = "not_applied"
    FAILED = "failed"
    PARTIALLY_APPLIED = "partially_applied"
    COMPLETED = "completed"

    def __str__(self) -> str:
        return self.name


class PullRequestId(EmbeddedModel):
    org_id: str
    repo_name: str
    pull_request: int


class PullRequestModel(Model):
    id: PullRequestId = Field(primary_field=True)
    draft: bool
    status: PullRequestStatus = Field(index=True)
    apply_status: ApplyStatus = Field(index=True, default=ApplyStatus.NOT_APPLIED)

    valid: bool | None = None
    in_sync: bool | None = None
    requires_manual_apply: bool | None = None
    supports_auto_merge: bool | None = None
    author_can_auto_merge: bool | None = None
    has_required_approvals: bool | None = None

    created_at: datetime = Field(index=True)
    updated_at: datetime = Field(index=True)

    closed_at: datetime | None = None
    merged_at: datetime | None = Field(index=True, default=None)

    def can_be_automerged(self) -> bool:
        return (
            self.valid is True
            # do not explicitly require that the config is in sync
            # only changes to the latest checked in config are applied
            # this allows projects to update the config even if its out-of-sync.
            # and self.in_sync is True
            and self.supports_auto_merge is True
            and (self.author_can_auto_merge is True or self.has_required_approvals is True)
        )


class StatisticsModel(Model):
    project_name: str = Field(primary_field=True)
    github_id: str = Field(index=True)
    two_factor_enforced: int
    total_repos: int
    archived_repos: int
    repos_with_secret_scanning: int
    repos_with_secret_scanning_push_protection: int
    repos_with_branch_protection: int
    repos_with_dependabot_alerts: int
    repos_with_dependabot_security_updates: int
    repos_with_private_vulnerability_reporting: int


class UserModel(Model):
    node_id: str = Field(primary_field=True)
    username: str
    email: str | None = None
    full_name: str | None = None
    projects: list[str] = Field(default_factory=list)


class PolicyId(EmbeddedModel):
    org_id: str
    policy_type: str


class PolicyModel(Model):
    id: PolicyId = Field(primary_field=True)
    path: str
    name: str | None = None
    description: str | None = None
    config: dict


class PolicyStatusModel(Model):
    id: PolicyId = Field(primary_field=True)
    status: dict = Field(default_factory=dict)


class BlueprintId(EmbeddedModel):
    org_id: str
    blueprint_type: str
    blueprint_id: str


class BlueprintModel(Model):
    id: BlueprintId = Field(primary_field=True)
    path: str
    name: str | None = None
    description: str | None = None
    recheck_needed: bool = True
    last_checked: datetime | None = Field(index=True, default=None)
    config: dict


class BlueprintStatusId(EmbeddedModel):
    org_id: str
    repo_name: str
    blueprint_id: str


class BlueprintStatus(str, Enum):
    NOT_CHECKED = "not_checked"
    SUCCESS = "success"
    FAILURE = "failure"
    REMEDIATION_PREPARED = "remediation_prepared"
    DISMISSED = "dismissed"
    RECHECK = "recheck"

    def __str__(self) -> str:
        return self.name


class BlueprintStatusModel(Model):
    id: BlueprintStatusId = Field(primary_field=True)

    updated_at: datetime = Field(index=True, default_factory=current_utc_time)
    status: BlueprintStatus = Field(default=BlueprintStatus.NOT_CHECKED)
    remediation_pr: int | None = Field(index=True, default=None)


class ScorecardId(EmbeddedModel):
    org_id: str
    repo_name: str


class ScorecardResultModel(Model):
    id: ScorecardId = Field(primary_field=True)

    updated_at: datetime = Field(index=True, default_factory=current_utc_time)
    score: float | None = None
    scorecard_version: str | None = None
    checks: list[dict[str, Any]] = Field(default_factory=list)
