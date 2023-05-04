# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

from dataclasses import dataclass, field
from typing import Any

from jsonbender import bend, S, OptionalS, K

from . import ModelObject, UNSET


@dataclass
class Repository(ModelObject):
    name: str = field(metadata={"key": True})
    description: str
    homepage: str
    private: bool
    has_issues: bool
    has_projects: bool
    has_wiki: bool
    default_branch: str
    allow_rebase_merge: bool
    allow_merge_commit: bool
    allow_squash_merge: bool
    allow_auto_merge: bool
    delete_branch_on_merge: bool
    allow_update_branch: bool
    squash_merge_commit_title: str
    squash_merge_commit_message: str
    merge_commit_title: str
    merge_commit_message: str
    archived: bool
    allow_forking: bool
    web_commit_signoff_required: bool
    secret_scanning: str
    secret_scanning_push_protection: str
    dependabot_alerts_enabled: bool
    branch_protection_rules: list[str]

    @classmethod
    def from_model(cls, data: dict[str, Any]) -> "Repository":
        mapping = {k: OptionalS(k, default=UNSET) for k in map(lambda x: x.name, cls.all_fields())}
        return cls(**bend(mapping, data))

    @classmethod
    def from_provider(cls, data: dict[str, Any]) -> "Repository":
        mapping = {k: S(k) for k in map(lambda x: x.name, cls.all_fields())}

        mapping.update({
            "branch_protection_rules": K([]),
            "secret_scanning":
                OptionalS("security_and_analysis", "secret_scanning", "status", default=UNSET),
            "secret_scanning_push_protection":
                OptionalS("security_and_analysis", "secret_scanning_push_protection", "status", default=UNSET)
        })

        return cls(**bend(mapping, data))
