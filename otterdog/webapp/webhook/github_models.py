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
from typing import Optional

from pydantic import BaseModel


class Installation(BaseModel):
    """The installation that is associated with the event."""

    id: int
    node_id: str


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
    repo: Repository


class PullRequest(BaseModel):
    """Represents a pull request."""

    id: int
    node_id: str
    number: int
    state: str
    locked: bool
    title: str
    body: Optional[str] = None
    draft: bool
    merged: bool
    merge_commit_sha: Optional[str] = None
    user: Actor

    head: Ref
    base: Ref


class Comment(BaseModel):
    """Represents a comment in an issue."""

    id: int
    node_id: str
    user: Actor
    body: str
    created_at: str
    updated_at: str


class Issue(BaseModel):
    """Represents an issue"""

    number: int
    node_id: str
    title: str
    state: str
    draft: bool
    body: Optional[str]
    html_url: str


class Event(ABC, BaseModel):
    """Base class of events"""

    installation: Optional[Installation] = None
    organization: Optional[Organization] = None
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
