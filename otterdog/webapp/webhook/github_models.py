#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

"""Data classes for events received via webhook from GitHub"""


from __future__ import annotations

from abc import ABC
from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class Installation(BaseModel):
    """The installation that is associated with the event."""

    id: int
    node_id: str | None = None


class Organization(BaseModel):
    """The organization that is associated with the event."""

    login: str
    id: int
    node_id: str


class Repository(BaseModel):
    """A reference to the repository."""

    id: int
    node_id: str
    name: str
    full_name: str
    private: bool
    owner: Actor
    default_branch: str


class Actor(BaseModel):
    """An actor, can be either of type 'User' or 'Organization'."""

    login: str
    id: int
    node_id: str
    type: str


class Ref(BaseModel):
    """A ref in a repository."""

    label: str
    ref: str
    sha: str
    user: Actor
    repo: Repository | None


class PullRequest(BaseModel):
    """Represents a pull request."""

    id: int
    node_id: str
    number: int
    state: str
    locked: bool
    title: str
    body: str | None = None
    draft: bool
    merged: bool | None = None
    merge_commit_sha: str | None = None
    user: Actor
    author_association: AuthorAssociation

    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None = None
    merged_at: datetime | None = None

    head: Ref
    base: Ref

    def get_pr_status(self) -> str:
        if self.state == "open":
            return self.state.upper()
        elif self.state == "closed":
            if self.merged_at is not None:
                return "MERGED"
            else:
                return "CLOSED"
        else:
            raise RuntimeError(f"unexpected state '{self.state}'")


class Comment(BaseModel):
    """Represents a comment in an issue."""

    id: int
    node_id: str
    user: Actor
    body: str
    created_at: str
    updated_at: str


class AssociatedPullRequest(BaseModel):
    """Indicates the associated pull request for an issue comment."""

    url: str
    html_url: str


class AuthorAssociation(str, Enum):
    COLLABORATOR = "COLLABORATOR"
    CONTRIBUTOR = "CONTRIBUTOR"
    FIRST_TIMER = "FIRST_TIME"
    FIRST_TIME_CONTRIBUTOR = "FIRST_TIME_CONTRIBUTOR"
    MANNEQUIN = "MANNEQUIN"
    MEMBER = "MEMBER"
    NONE = "NONE"
    OWNER = "OWNER"

    def __str__(self) -> str:
        return self.name


class Issue(BaseModel):
    """Represents an issue"""

    number: int
    node_id: str
    title: str
    state: str
    user: Actor | None = None
    author_association: AuthorAssociation
    draft: bool | None = None
    body: str | None = None
    pull_request: AssociatedPullRequest | None = None
    html_url: str


class Event(ABC, BaseModel):
    """Base class of events"""

    installation: Installation | None = None
    organization: Organization | None = None
    sender: Actor


class PullRequestEvent(Event):
    """A payload sent for pull request specific events."""

    action: str
    number: int
    pull_request: PullRequest
    repository: Repository


class PushEvent(Event):
    """A payload sent for push events."""

    ref: str
    before: str
    after: str

    repository: Repository

    created: bool
    deleted: bool
    forced: bool


class IssueCommentEvent(Event):
    """A payload sent for issue comment events."""

    action: str
    issue: Issue
    comment: Comment
    repository: Repository


class InstallationEvent(Event):
    """A payload sent for installation events."""

    action: str
