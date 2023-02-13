# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

import json
from typing import Any

import utils
from config import OtterdogConfig
from diff import DiffOperation


class PlanOperation(DiffOperation):
    def __init__(self, config: OtterdogConfig):
        super().__init__(config)

    def handle_modified_settings(self, org_id: str, modified_settings: dict[str, (Any, Any)]) -> None:
        for key, (expected_value, current_value) in modified_settings.items():
            utils.print_info(f"  {key}: expected '{expected_value}' but was '{current_value}'")

    def handle_modified_webhook(self, org_id: str, webhook_id: str, modified_webhook: dict[str, (Any, Any)]) -> None:
        for key, (expected_value, current_value) in modified_webhook.items():
            msg = f"  webhook['{webhook_id}'].config.{key}: expected '{expected_value}' but was '{current_value}'"
            utils.print_info(msg)

    def handle_new_webhook(self,
                           org_id: str,
                           data: dict[str, Any]) -> None:
        utils.print_info(f"  new webhook with data:\n{json.dumps(data, indent=2)}")

    def handle_modified_repo(self, org_id: str, repo_name: str, modified_repo: dict[str, (Any, Any)]) -> None:
        for key, (expected_value, current_value) in modified_repo.items():
            msg = f"  repo['{repo_name}'].{key}: expected '{expected_value}' but was '{current_value}'"
            utils.print_info(msg)

    def handle_new_repo(self,
                        org_id: str,
                        data: dict[str, Any]) -> None:
        utils.print_info(f"  new repo with data:\n{json.dumps(data, indent=2)}")

    def handle_modified_rule(self,
                             org_id: str,
                             repo_name: str,
                             rule_pattern: str,
                             rule_id: str,
                             modified_rule: dict[str, Any]) -> None:
        for key, (expected_value, current_value) in modified_rule.items():
            msg = f"  branch_protection_rule['{rule_pattern}'].{key}: " \
                  f"expected '{expected_value}' but was '{current_value}'"
            utils.print_info(msg)

    def handle_new_rule(self, org_id: str, repo_name: str, repo_id: str, data: dict[str, Any]) -> None:
        utils.print_info(f"  new branch_protection_rule for repo '{repo_name}'"
                         f"with data:\n{json.dumps(data, indent=2)}")

    def handle_finish(self, differences: int) -> None:
        utils.print_info(f"found {differences} difference(s)")
