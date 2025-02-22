#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

import dataclasses
from logging import getLogger
from typing import TYPE_CHECKING, Any

from odmantic import query
from quart import current_app

from otterdog.utils import unwrap
from otterdog.webapp import mongo
from otterdog.webapp.utils import (
    current_utc_time,
    get_rest_api_for_app,
    refresh_global_blueprints,
    refresh_global_policies,
)

from .models import (
    ApplyStatus,
    BlueprintId,
    BlueprintModel,
    BlueprintStatus,
    BlueprintStatusId,
    BlueprintStatusModel,
    ConfigurationModel,
    InstallationModel,
    InstallationStatus,
    PolicyId,
    PolicyModel,
    PolicyStatusModel,
    PullRequestId,
    PullRequestModel,
    PullRequestStatus,
    ScorecardId,
    ScorecardResultModel,
    StatisticsModel,
    TaskModel,
    TaskStatus,
    UserModel,
)

if TYPE_CHECKING:
    from datetime import datetime

    from odmantic.query import QueryExpression

    from otterdog.config import OtterdogConfig
    from otterdog.webapp.blueprints import Blueprint
    from otterdog.webapp.policies import Policy
    from otterdog.webapp.webhook.github_models import PullRequest

logger = getLogger(__name__)


async def update_installation_status(installation_id: int, action: str) -> None:
    logger.info(f"updating installation status for installation with id '{installation_id}': {action}")

    match action:
        case "created":
            policies = await refresh_global_policies()
            blueprints = await refresh_global_blueprints()
            await add_app_installation(installation_id, policies, blueprints)

        case "deleted":
            installation = await mongo.odm.find_one(
                InstallationModel, InstallationModel.installation_id == installation_id
            )

            if installation is not None:
                installation.installation_id = 0
                installation.installation_status = InstallationStatus.NOT_INSTALLED
                await mongo.odm.save(installation)
                await cleanup_data()

        case "suspend":
            installation = await mongo.odm.find_one(
                InstallationModel, InstallationModel.installation_id == installation_id
            )

            if installation is not None:
                installation.installation_status = InstallationStatus.SUSPENDED
                await mongo.odm.save(installation)

        case "unsuspend":
            installation = await mongo.odm.find_one(
                InstallationModel, InstallationModel.installation_id == installation_id
            )

            if installation is not None:
                installation.installation_status = InstallationStatus.INSTALLED
                await mongo.odm.save(installation)

                await update_data_for_installation(installation)

        case _:
            pass


async def update_installations_from_config(
    otterdog_config: OtterdogConfig,
    global_policies: list[Policy],
    global_blueprints: list[Blueprint],
    update_installations: bool = True,
) -> None:
    logger.info("updating installations from otterdog config")

    existing_installations = {x.github_id for x in await get_installations()}

    projects_to_update: set[str] = set()

    async with mongo.odm.session() as session:
        # process all projects present in the otterdog config
        for github_id in otterdog_config.organization_names:
            project_name = otterdog_config.get_project_name(github_id)
            if project_name is None:
                continue

            org_config = otterdog_config.get_organization_config(project_name)

            model = await get_installation_by_github_id(github_id)
            if model is None:
                # check if an installation for the project_name already exists
                # in this case the github_id has changed, we need to delete this instance
                # as we cant change the primary key.
                model = await get_installation_by_project_name(project_name)
                if model is not None:
                    await mongo.odm.delete(model)

                model = InstallationModel(  # type: ignore
                    installation_id=0,
                    installation_status=InstallationStatus.NOT_INSTALLED,
                    project_name=project_name,
                    github_id=github_id,
                    config_repo=org_config.config_repo,
                    base_template=org_config.base_template,
                )

                projects_to_update.add(project_name)
            else:
                if model.project_name != project_name:
                    model.project_name = project_name
                    projects_to_update.add(project_name)

                if model.base_template != org_config.base_template:
                    model.base_template = org_config.base_template
                    projects_to_update.add(project_name)

                if model.config_repo != org_config.config_repo:
                    model.config_repo = org_config.config_repo
                    projects_to_update.add(project_name)

            await session.save(model)

            if github_id in existing_installations:
                existing_installations.remove(github_id)

        # remove all remaining installations which are not present in the otterdog config
        for github_id in existing_installations:
            await session.remove(InstallationModel, InstallationModel.github_id == github_id)

    # remove all PullRequest and Statistics data for invalid installations
    await cleanup_data()

    if update_installations is True:
        await update_app_installations(global_policies, global_blueprints, projects_to_update)


async def cleanup_data() -> None:
    valid_orgs = [x.github_id for x in await get_installations()]
    await cleanup_pull_requests(valid_orgs)
    await cleanup_statistics(valid_orgs)
    await cleanup_configurations(valid_orgs)
    await cleanup_policies(valid_orgs)
    await cleanup_policies_status(valid_orgs)
    await cleanup_blueprints(valid_orgs)
    await cleanup_blueprints_status(valid_orgs)


async def update_app_installations(
    global_policies: list[Policy],
    global_blueprints: list[Blueprint],
    project_names_to_force_update: set[str] | None = None,
) -> None:
    logger.info("updating app installations")

    rest_api = get_rest_api_for_app()
    all_installations = await rest_api.app.get_app_installations()

    async with mongo.odm.session() as session:
        for app_installation in all_installations:
            installation_id = app_installation["id"]
            github_id = app_installation["account"]["login"]
            suspended_at = app_installation["suspended_at"]
            installation_status = InstallationStatus.INSTALLED if suspended_at is None else InstallationStatus.SUSPENDED

            model = await get_installation_by_github_id(github_id)
            if model is not None:
                model.installation_id = int(installation_id)
                model.installation_status = installation_status

                await session.save(model)

    for installation in await get_active_installations():
        configuration_model = await get_configuration_by_github_id(installation.github_id)
        if configuration_model is None or (
            project_names_to_force_update is not None and installation.project_name in project_names_to_force_update
        ):
            await update_data_for_installation(installation)

        await update_policies_and_blueprints_for_installation(installation, global_policies, global_blueprints)


async def add_app_installation(
    installation_id: int,
    global_policies: list[Policy],
    global_blueprints: list[Blueprint],
):
    logger.info("adding app installation for id '%d'", installation_id)

    rest_api = get_rest_api_for_app()
    app_installation = await rest_api.app.get_app_installation(installation_id)

    async with mongo.odm.session() as session:
        installation_id = app_installation["id"]
        github_id = app_installation["account"]["login"]
        suspended_at = app_installation["suspended_at"]
        installation_status = InstallationStatus.INSTALLED if suspended_at is None else InstallationStatus.SUSPENDED

        installation_model = await get_installation_by_github_id(github_id)
        if installation_model is not None:
            installation_model.installation_id = int(installation_id)
            installation_model.installation_status = installation_status

            await session.save(installation_model)
        else:
            return

    await update_data_for_installation(installation_model)
    await update_policies_and_blueprints_for_installation(installation_model, global_policies, global_blueprints)


async def update_data_for_installation(installation: InstallationModel) -> None:
    from otterdog.webapp.tasks.fetch_all_pull_requests import FetchAllPullRequestsTask
    from otterdog.webapp.tasks.fetch_config import FetchConfigTask

    config_repo = unwrap(installation.config_repo)

    current_app.add_background_task(
        FetchConfigTask(
            installation.installation_id,
            installation.github_id,
            config_repo,
        )
    )

    current_app.add_background_task(
        FetchAllPullRequestsTask(
            installation.installation_id,
            installation.github_id,
            config_repo,
        )
    )


async def update_policies_and_blueprints_for_installation(
    installation: InstallationModel,
    global_policies: list[Policy],
    global_blueprints: list[Blueprint],
) -> None:
    from otterdog.webapp.tasks.fetch_blueprints import FetchBlueprintsTask
    from otterdog.webapp.tasks.fetch_policies import FetchPoliciesTask

    config_repo = unwrap(installation.config_repo)

    current_app.add_background_task(
        FetchPoliciesTask(
            installation.installation_id,
            installation.github_id,
            config_repo,
            global_policies,
        )
    )

    current_app.add_background_task(
        FetchBlueprintsTask(
            installation.installation_id,
            installation.github_id,
            config_repo,
            global_blueprints,
        )
    )


async def get_installation(installation_id: int) -> InstallationModel | None:
    return await mongo.odm.find_one(InstallationModel, InstallationModel.installation_id == installation_id)


async def get_installation_by_github_id(github_id: str) -> InstallationModel | None:
    return await mongo.odm.find_one(InstallationModel, InstallationModel.github_id == github_id)


async def get_installation_by_project_name(project_name: str) -> InstallationModel | None:
    return await mongo.odm.find_one(InstallationModel, InstallationModel.project_name == project_name)


async def get_all_installations_count() -> int:
    return await mongo.odm.count(InstallationModel)


async def get_installations() -> list[InstallationModel]:
    return await mongo.odm.find(InstallationModel, sort=InstallationModel.project_name)


async def get_active_installations() -> list[InstallationModel]:
    return await mongo.odm.find(
        InstallationModel, InstallationModel.installation_status == InstallationStatus.INSTALLED
    )


async def get_tasks(limit: int) -> list[TaskModel]:
    return await mongo.odm.find(TaskModel, limit=limit, sort=query.desc(TaskModel.created_at))


async def get_tasks_paged(params: dict[str, str]) -> tuple[list[TaskModel], int]:
    page_index = 1
    page_size = 20
    sort_field = "created_at"
    sort_order = "desc"

    queries: list[QueryExpression] = []

    for k, v in params.items():
        match k:
            case "pageIndex":
                page_index = int(v)
            case "pageSize":
                page_size = int(v)
            case "sortField":
                sort_field = v
            case "sortOrder":
                sort_order = v
            case _:
                if v:
                    queries.append(query.match(TaskModel.__dict__[k], v))

    sort = (
        query.desc(TaskModel.__dict__[sort_field])
        if sort_order == "desc"
        else query.asc(TaskModel.__dict__[sort_field])
    )

    skip = (page_index - 1) * page_size
    return (
        await mongo.odm.find(
            TaskModel,
            *queries,
            skip=skip,
            limit=page_size,
            sort=sort,
        ),
        await mongo.odm.count(TaskModel, *queries),
    )


async def get_configurations() -> list[ConfigurationModel]:
    return await mongo.odm.find(ConfigurationModel)


async def get_configuration_by_github_id(github_id: str) -> ConfigurationModel | None:
    return await mongo.odm.find_one(ConfigurationModel, ConfigurationModel.github_id == github_id)


async def get_configuration_by_project_name(project_name: str) -> ConfigurationModel | None:
    return await mongo.odm.find_one(ConfigurationModel, ConfigurationModel.project_name == project_name)


async def cleanup_configurations(valid_orgs: list[str]) -> None:
    await mongo.odm.remove(ConfigurationModel, query.not_in(ConfigurationModel.github_id, valid_orgs))


async def create_task(task: TaskModel) -> None:
    await mongo.odm.save(task)


async def schedule_task(task: TaskModel) -> None:
    task.status = TaskStatus.SCHEDULED
    await mongo.odm.save(task)


async def finish_task(task: TaskModel) -> None:
    task.status = TaskStatus.FINISHED
    task.updated_at = current_utc_time()
    await mongo.odm.save(task)


async def fail_task(task: TaskModel, exception: Exception) -> None:
    task.status = TaskStatus.FAILED
    task.updated_at = current_utc_time()
    task.log = str(exception)
    await mongo.odm.save(task)


async def get_latest_sync_task_for_organization(org_id: str, repo_name: str) -> TaskModel | None:
    tasks = await mongo.odm.find(
        TaskModel,
        TaskModel.type == "CheckConfigurationInSyncTask",
        TaskModel.status != TaskStatus.CREATED,
        TaskModel.org_id == org_id,
        TaskModel.repo_name == repo_name,
        sort=query.desc(TaskModel.created_at),
        limit=1,
    )

    if len(tasks) == 1:
        return tasks[0]
    else:
        return None


async def save_config(config: ConfigurationModel) -> None:
    await mongo.odm.save(config)


async def find_pull_request(owner: str, repo: str, pull_request: int) -> PullRequestModel | None:
    return await mongo.odm.find_one(
        PullRequestModel,
        PullRequestModel.id.org_id == owner,
        PullRequestModel.id.repo_name == repo,
        PullRequestModel.id.pull_request == pull_request,
    )


async def update_or_create_pull_request(
    owner: str,
    repo: str,
    pull_request: PullRequest,
    valid: bool | None = None,
    in_sync: bool | None = None,
    requires_manual_apply: bool | None = None,
    supports_auto_merge: bool | None = None,
    author_can_auto_merge: bool | None = None,
    has_required_approvals: bool | None = None,
    apply_status: ApplyStatus | None = None,
) -> PullRequestModel:
    pull_request_status = PullRequestStatus[pull_request.get_pr_status()]

    pr_model = await find_pull_request(owner, repo, pull_request.number)
    if pr_model is None:
        pr_model = PullRequestModel(  # type: ignore
            id=PullRequestId(org_id=owner, repo_name=repo, pull_request=pull_request.number),
            draft=pull_request.draft,
            status=pull_request_status,
            created_at=pull_request.created_at,
            updated_at=pull_request.updated_at,
            closed_at=pull_request.closed_at,
            merged_at=pull_request.merged_at,
        )
    else:
        pr_model.draft = pull_request.draft
        pr_model.status = pull_request_status
        pr_model.created_at = pull_request.created_at
        pr_model.updated_at = pull_request.updated_at
        pr_model.closed_at = pull_request.closed_at
        pr_model.merged_at = pull_request.merged_at

    if apply_status is not None:
        pr_model.apply_status = apply_status

    if valid is not None:
        pr_model.valid = valid

    if in_sync is not None:
        pr_model.in_sync = in_sync

    if requires_manual_apply is not None:
        pr_model.requires_manual_apply = requires_manual_apply

    if supports_auto_merge is not None:
        pr_model.supports_auto_merge = supports_auto_merge

    if author_can_auto_merge is not None:
        pr_model.author_can_auto_merge = author_can_auto_merge

    if has_required_approvals is not None:
        pr_model.has_required_approvals = has_required_approvals

    await update_pull_request(pr_model)
    return pr_model


async def update_pull_request(pull_request: PullRequestModel) -> None:
    await mongo.odm.save(pull_request)


async def get_open_or_incomplete_pull_requests() -> list[PullRequestModel]:
    return await mongo.odm.find(
        PullRequestModel,
        _open_or_incomplete_pull_requests_query(),
        sort=query.desc(PullRequestModel.created_at),
    )


async def get_open_or_incomplete_pull_requests_count() -> int:
    return await mongo.odm.count(
        PullRequestModel,
        _open_or_incomplete_pull_requests_query(),
    )


def _open_or_incomplete_pull_requests_query() -> QueryExpression:
    return query.or_(
        PullRequestModel.status == PullRequestStatus.OPEN,
        query.and_(
            PullRequestModel.status == PullRequestStatus.MERGED,
            PullRequestModel.apply_status != ApplyStatus.COMPLETED,
        ),
    )


async def get_merged_pull_requests_count() -> int:
    return await mongo.odm.count(
        PullRequestModel,
        _merged_pull_requests_query(),
    )


def _merged_pull_requests_query() -> QueryExpression:
    return query.and_(
        PullRequestModel.status == PullRequestStatus.MERGED,
        PullRequestModel.apply_status == ApplyStatus.COMPLETED,
    )


async def get_open_pull_requests_paged(params: dict[str, str]) -> tuple[list[PullRequestModel], int]:
    page_index = 1
    page_size = 20
    sort_field_name = "created_at"
    sort_order = "desc"

    queries: list[QueryExpression] = [_open_or_incomplete_pull_requests_query()]

    for k, v in params.items():
        match k:
            case "pageIndex":
                page_index = int(v)
            case "pageSize":
                page_size = int(v)
            case "sortField":
                sort_field_name = v
            case "sortOrder":
                sort_order = v
            case _:
                if v:
                    if k.startswith("id["):
                        match k:
                            case "id[org_id]":
                                queries.append(query.match(PullRequestModel.id.org_id, v))
                            case "id[repo_name]":
                                queries.append(query.match(PullRequestModel.id.repo_name, v))
                            case "id[pull_request]":
                                queries.append(query.match(PullRequestModel.id.pull_request, int(v)))  # type: ignore
                            case _:
                                raise RuntimeError(f"unexpected query field '{k}'")
                    else:
                        # js grid send either "true" or "false" for boolean values
                        # need to convert it to a bool value in python
                        if v.lower() in ("true", "false"):
                            queries.append(query.eq(PullRequestModel.__dict__[k], v.lower() == "true"))
                        else:
                            queries.append(query.match(PullRequestModel.__dict__[k], v))

    if sort_field_name.startswith("id."):
        match sort_field_name:
            case "id.org_id":
                sort_field = PullRequestModel.id.org_id
            case "id.repo_name":
                sort_field = PullRequestModel.id.repo_name
            case "id.pull_request":
                sort_field = PullRequestModel.id.pull_request  # type: ignore
            case _:
                raise RuntimeError(f"unexpected sort field '{sort_field_name}'")
    else:
        sort_field = PullRequestModel.__dict__[sort_field_name]

    sort = query.desc(sort_field) if sort_order == "desc" else query.asc(sort_field)
    skip = (page_index - 1) * page_size
    return (
        await mongo.odm.find(
            PullRequestModel,
            *queries,
            skip=skip,
            limit=page_size,
            sort=sort,
        ),
        await mongo.odm.count(PullRequestModel, *queries),
    )


async def get_merged_pull_requests_paged(params: dict[str, str]) -> tuple[list[PullRequestModel], int]:
    page_index = 1
    page_size = 20
    sort_field_name = "merged_at"
    sort_order = "desc"

    queries: list[QueryExpression] = [_merged_pull_requests_query()]

    for k, v in params.items():
        match k:
            case "pageIndex":
                page_index = int(v)
            case "pageSize":
                page_size = int(v)
            case "sortField":
                sort_field_name = v
            case "sortOrder":
                sort_order = v
            case _:
                if v:
                    if k.startswith("id["):
                        match k:
                            case "id[org_id]":
                                queries.append(query.match(PullRequestModel.id.org_id, v))
                            case "id[repo_name]":
                                queries.append(query.match(PullRequestModel.id.repo_name, v))
                            case "id[pull_request]":
                                queries.append(query.match(PullRequestModel.id.pull_request, int(v)))  # type: ignore
                            case _:
                                raise RuntimeError(f"unexpected query field '{k}'")
                    else:
                        queries.append(query.match(PullRequestModel.__dict__[k], v))

    if sort_field_name.startswith("id."):
        match sort_field_name:
            case "id.org_id":
                sort_field = PullRequestModel.id.org_id
            case "id.repo_name":
                sort_field = PullRequestModel.id.repo_name
            case "id.pull_request":
                sort_field = PullRequestModel.id.pull_request  # type: ignore
            case _:
                raise RuntimeError(f"unexpected sort field '{sort_field_name}'")
    else:
        sort_field = PullRequestModel.__dict__[sort_field_name]

    sort = query.desc(sort_field) if sort_order == "desc" else query.asc(sort_field)
    skip = (page_index - 1) * page_size
    return (
        await mongo.odm.find(
            PullRequestModel,
            *queries,
            skip=skip,
            limit=page_size,
            sort=sort,
        ),
        await mongo.odm.count(PullRequestModel, *queries),
    )


async def cleanup_pull_requests(valid_orgs: list[str]) -> None:
    await mongo.odm.remove(PullRequestModel, query.not_in(PullRequestModel.id.org_id, valid_orgs))


async def save_statistics(model: StatisticsModel) -> None:
    await mongo.odm.save(model)


@dataclasses.dataclass(frozen=True)
class Statistics:
    total_projects: int = 0
    projects_with_two_factor_auth_enforced: int = 0
    total_repos: int = 0
    archived_repos: int = 0
    repos_with_branch_protection: int = 0
    repos_with_secret_scanning: int = 0
    repos_with_secret_scanning_and_protection: int = 0
    repos_with_dependabot_alerts: int = 0
    repos_with_dependabot_security_updates: int = 0
    repos_with_private_vulnerability_reporting: int = 0

    @property
    def active_repos(self) -> int:
        return self.total_repos - self.archived_repos


async def get_statistics() -> Statistics:
    pipeline = [
        {
            "$group": {
                "_id": None,
                "total_projects": {"$sum": 1},
                "two_factor_enforced": {"$sum": "$two_factor_enforced"},
                "total_repos": {"$sum": "$total_repos"},
                "archived_repos": {"$sum": "$archived_repos"},
                "repos_with_branch_protection": {"$sum": "$repos_with_branch_protection"},
                "repos_with_secret_scanning": {"$sum": "$repos_with_secret_scanning"},
                "repos_with_secret_scanning_push_protection": {"$sum": "$repos_with_secret_scanning_push_protection"},
                "repos_with_dependabot_alerts": {"$sum": "$repos_with_dependabot_alerts"},
                "repos_with_dependabot_security_updates": {"$sum": "$repos_with_dependabot_security_updates"},
                "repos_with_private_vulnerability_reporting": {"$sum": "$repos_with_private_vulnerability_reporting"},
            },
        }
    ]

    collection = mongo.odm.get_collection(StatisticsModel)
    stats_list = await collection.aggregate(pipeline).to_list(1)
    if stats_list is None or len(stats_list) == 0:
        return Statistics()
    else:
        stats = stats_list[0]
        return Statistics(
            stats["total_projects"],
            stats["two_factor_enforced"],
            stats["total_repos"],
            stats["archived_repos"],
            stats["repos_with_branch_protection"],
            stats["repos_with_secret_scanning"],
            stats["repos_with_secret_scanning_push_protection"],
            stats["repos_with_dependabot_alerts"],
            stats["repos_with_dependabot_security_updates"],
            stats["repos_with_private_vulnerability_reporting"],
        )


async def cleanup_statistics(valid_orgs: list[str]) -> None:
    await mongo.odm.remove(StatisticsModel, query.not_in(StatisticsModel.github_id, valid_orgs))


async def get_user(node_id: str) -> UserModel | None:
    return await mongo.odm.find_one(UserModel, UserModel.node_id == node_id)


async def save_user(user: UserModel) -> None:
    await mongo.odm.save(user)


async def get_policies(owner: str) -> list[PolicyModel]:
    return await mongo.odm.find(
        PolicyModel,
        PolicyModel.id.org_id == owner,
        sort=PolicyModel.id.policy_type,
    )


async def find_policy(owner: str, policy_type: str) -> PolicyModel | None:
    return await mongo.odm.find_one(
        PolicyModel,
        PolicyModel.id.org_id == owner,
        PolicyModel.id.policy_type == policy_type,
    )


async def update_or_create_policy(owner: str, policy: Policy) -> None:
    policy_model = await find_policy(owner, policy.type.value)
    if policy_model is None:
        policy_model = PolicyModel(
            id=PolicyId(org_id=owner, policy_type=policy.type.value),
            path=policy.path,
            name=policy.name,
            description=policy.description,
            config=policy.config,
        )
    else:
        policy_model.path = policy.path
        policy_model.name = policy.name
        policy_model.description = policy.description
        policy_model.config = policy.config

    await mongo.odm.save(policy_model)


async def cleanup_policies(valid_orgs: list[str]) -> None:
    await mongo.odm.remove(PolicyModel, query.not_in(PolicyModel.id.org_id, valid_orgs))


async def cleanup_policies_of_owner(owner: str, valid_types: list[str]) -> None:
    await mongo.odm.remove(
        PolicyModel, PolicyModel.id.org_id == owner, query.not_in(PolicyModel.id.policy_type, valid_types)
    )


async def get_policies_status(owner: str) -> list[PolicyStatusModel]:
    return await mongo.odm.find(
        PolicyStatusModel,
        PolicyStatusModel.id.org_id == owner,
        sort=PolicyModel.id.policy_type,
    )


async def find_policy_status(owner: str, policy_type: str) -> PolicyStatusModel | None:
    return await mongo.odm.find_one(
        PolicyStatusModel,
        PolicyStatusModel.id.org_id == owner,
        PolicyStatusModel.id.policy_type == policy_type,
    )


async def create_policy_status_if_needed(owner: str, policy: Policy, status: dict[str, Any]) -> bool:
    policy_status_model = await find_policy_status(owner, policy.type.value)
    if policy_status_model is None:
        policy_status_model = PolicyStatusModel(
            id=PolicyId(org_id=owner, policy_type=policy.type.value),
            status=status,
        )

        await mongo.odm.save(policy_status_model)
        return True

    return False


async def increment_or_create_policy_status(owner: str, policy: Policy, status_diff: dict[str, Any]) -> None:
    if await create_policy_status_if_needed(owner, policy, status_diff) is True:
        return

    collection = mongo.odm.get_collection(PolicyStatusModel)
    update_filter = {"_id": {"org_id": owner, "policy_type": policy.type.value}}
    update_data = {"$inc": {f"status.{k}": v for k, v in status_diff.items()}}

    await collection.update_one(
        update_filter,
        update_data,
    )


async def cleanup_policies_status(valid_orgs: list[str]) -> None:
    await mongo.odm.remove(PolicyStatusModel, query.not_in(PolicyStatusModel.id.org_id, valid_orgs))


async def cleanup_policies_status_of_owner(owner: str, valid_types: list[str]) -> None:
    await mongo.odm.remove(
        PolicyStatusModel,
        PolicyStatusModel.id.org_id == owner,
        query.not_in(PolicyStatusModel.id.policy_type, valid_types),
    )


async def get_blueprints(owner: str) -> list[BlueprintModel]:
    return await mongo.odm.find(
        BlueprintModel,
        BlueprintModel.id.org_id == owner,
        sort=BlueprintModel.id.blueprint_id,
    )


async def get_blueprints_by_last_checked_time(limit: int) -> list[BlueprintModel]:
    return await mongo.odm.find(
        BlueprintModel,
        limit=limit,
        sort=query.asc(BlueprintModel.last_checked),
    )


async def find_blueprint(owner: str, blueprint_id: str) -> BlueprintModel | None:
    return await mongo.odm.find_one(
        BlueprintModel,
        BlueprintModel.id.org_id == owner,
        BlueprintModel.id.blueprint_id == blueprint_id,
    )


async def update_or_create_blueprint(owner: str, blueprint: Blueprint) -> bool:
    blueprint_model = await find_blueprint(owner, blueprint.id)
    if blueprint_model is None:
        blueprint_model = BlueprintModel(
            id=BlueprintId(org_id=owner, blueprint_type=blueprint.type.value, blueprint_id=blueprint.id),
            path=blueprint.path,
            name=blueprint.name,
            description=blueprint.description,
            config=blueprint.config,
        )
    else:
        recheck = False

        def update_if_changed(obj: BlueprintModel, attr: str, value: Any) -> bool:
            if obj.__getattribute__(attr) != value:
                obj.__setattr__(attr, value)
                return True
            else:
                return False

        recheck = recheck or update_if_changed(blueprint_model, "path", blueprint.path)
        recheck = recheck or update_if_changed(blueprint_model, "name", blueprint.name)
        recheck = recheck or update_if_changed(blueprint_model, "description", blueprint.description)
        recheck = recheck or update_if_changed(blueprint_model, "config", blueprint.config)

        blueprint_model.recheck_needed = recheck

    await save_blueprint(blueprint_model)
    return blueprint_model.recheck_needed


async def save_blueprint(blueprint_model: BlueprintModel) -> None:
    await mongo.odm.save(blueprint_model)


async def cleanup_blueprints(valid_orgs: list[str]) -> None:
    await mongo.odm.remove(BlueprintModel, query.not_in(BlueprintModel.id.org_id, valid_orgs))


async def cleanup_blueprints_of_owner(owner: str, valid_ids: list[str]) -> None:
    await mongo.odm.remove(
        BlueprintModel, BlueprintModel.id.org_id == owner, query.not_in(BlueprintModel.id.blueprint_id, valid_ids)
    )


async def get_blueprints_status(owner: str) -> list[BlueprintStatusModel]:
    return await mongo.odm.find(
        BlueprintStatusModel,
        BlueprintStatusModel.id.org_id == owner,
        sort=BlueprintStatusModel.id.repo_name,
    )


async def get_blueprints_status_for_repo(owner: str, repo_name: str) -> list[BlueprintStatusModel]:
    return await mongo.odm.find(
        BlueprintStatusModel,
        BlueprintStatusModel.id.org_id == owner,
        BlueprintStatusModel.id.repo_name == repo_name,
        sort=BlueprintStatusModel.id.blueprint_id,
    )


async def get_blueprints_status_with_remediation() -> list[BlueprintStatusModel]:
    return await mongo.odm.find(
        BlueprintStatusModel,
        BlueprintStatusModel.status == BlueprintStatus.REMEDIATION_PREPARED,
        sort=query.desc(PullRequestModel.created_at),
    )


async def find_blueprint_status(owner: str, repo_name: str, blueprint_id: str) -> BlueprintStatusModel | None:
    return await mongo.odm.find_one(
        BlueprintStatusModel,
        BlueprintStatusModel.id.org_id == owner,
        BlueprintStatusModel.id.repo_name == repo_name,
        BlueprintStatusModel.id.blueprint_id == blueprint_id,
    )


async def find_blueprint_status_by_pr(owner: str, repo_name: str, pr_number: int) -> BlueprintStatusModel | None:
    return await mongo.odm.find_one(
        BlueprintStatusModel,
        BlueprintStatusModel.id.org_id == owner,
        BlueprintStatusModel.id.repo_name == repo_name,
        BlueprintStatusModel.remediation_pr == pr_number,
    )


async def update_or_create_blueprint_status(
    owner: str,
    repo_name: str,
    blueprint_id: str,
    status: BlueprintStatus | None = None,
    remediation_pr: int | None = None,
) -> None:
    blueprint_status_model = await find_blueprint_status(owner, repo_name, blueprint_id)
    if blueprint_status_model is None:
        blueprint_status_model = BlueprintStatusModel(
            id=BlueprintStatusId(org_id=owner, repo_name=repo_name, blueprint_id=blueprint_id),
        )

    if status is not None:
        blueprint_status_model.status = status

    blueprint_status_model.remediation_pr = remediation_pr

    await mongo.odm.save(blueprint_status_model)


async def save_blueprint_status(blueprint_status: BlueprintStatusModel) -> None:
    await mongo.odm.save(blueprint_status)


async def get_blueprints_with_remediations_paged(params: dict[str, str]) -> tuple[list[BlueprintStatusModel], int]:
    page_index = 1
    page_size = 20
    sort_field_name = "updated_at"
    sort_order = "desc"

    queries: list[QueryExpression] = [query.match(BlueprintStatusModel.status, BlueprintStatus.REMEDIATION_PREPARED)]

    for k, v in params.items():
        match k:
            case "pageIndex":
                page_index = int(v)
            case "pageSize":
                page_size = int(v)
            case "sortField":
                sort_field_name = v
            case "sortOrder":
                sort_order = v
            case _:
                if v:
                    if k.startswith("id["):
                        match k:
                            case "id[org_id]":
                                queries.append(query.match(BlueprintStatusModel.id.org_id, v))
                            case "id[repo_name]":
                                queries.append(query.match(BlueprintStatusModel.id.repo_name, v))
                            case "id[blueprint_id]":
                                queries.append(query.match(BlueprintStatusModel.id.blueprint_id, v))
                            case _:
                                raise RuntimeError(f"unexpected query field '{k}'")
                    else:
                        queries.append(query.match(BlueprintStatusModel.__dict__[k], v))

    if sort_field_name.startswith("id."):
        match sort_field_name:
            case "id.org_id":
                sort_field = BlueprintStatusModel.id.org_id
            case "id.repo_name":
                sort_field = BlueprintStatusModel.id.repo_name
            case "id.blueprint_id":
                sort_field = BlueprintStatusModel.id.blueprint_id
            case _:
                raise RuntimeError(f"unexpected sort field '{sort_field_name}'")
    else:
        sort_field = BlueprintStatusModel.__dict__[sort_field_name]

    sort = query.desc(sort_field) if sort_order == "desc" else query.asc(sort_field)
    skip = (page_index - 1) * page_size
    return (
        await mongo.odm.find(
            BlueprintStatusModel,
            *queries,
            skip=skip,
            limit=page_size,
            sort=sort,
        ),
        await mongo.odm.count(BlueprintStatusModel, *queries),
    )


async def get_dismissed_blueprints_paged(params: dict[str, str]) -> tuple[list[BlueprintStatusModel], int]:
    page_index = 1
    page_size = 20
    sort_field_name = "updated_at"
    sort_order = "desc"

    queries: list[QueryExpression] = [query.match(BlueprintStatusModel.status, BlueprintStatus.DISMISSED)]

    for k, v in params.items():
        match k:
            case "pageIndex":
                page_index = int(v)
            case "pageSize":
                page_size = int(v)
            case "sortField":
                sort_field_name = v
            case "sortOrder":
                sort_order = v
            case _:
                if v:
                    if k.startswith("id["):
                        match k:
                            case "id[org_id]":
                                queries.append(query.match(BlueprintStatusModel.id.org_id, v))
                            case "id[repo_name]":
                                queries.append(query.match(BlueprintStatusModel.id.repo_name, v))
                            case "id[blueprint_id]":
                                queries.append(query.match(BlueprintStatusModel.id.blueprint_id, v))
                            case _:
                                raise RuntimeError(f"unexpected query field '{k}'")
                    else:
                        queries.append(query.match(BlueprintStatusModel.__dict__[k], v))

    if sort_field_name.startswith("id."):
        match sort_field_name:
            case "id.org_id":
                sort_field = BlueprintStatusModel.id.org_id
            case "id.repo_name":
                sort_field = BlueprintStatusModel.id.repo_name
            case "id.blueprint_id":
                sort_field = BlueprintStatusModel.id.blueprint_id
            case _:
                raise RuntimeError(f"unexpected sort field '{sort_field_name}'")
    else:
        sort_field = BlueprintStatusModel.__dict__[sort_field_name]

    sort = query.desc(sort_field) if sort_order == "desc" else query.asc(sort_field)
    skip = (page_index - 1) * page_size
    return (
        await mongo.odm.find(
            BlueprintStatusModel,
            *queries,
            skip=skip,
            limit=page_size,
            sort=sort,
        ),
        await mongo.odm.count(BlueprintStatusModel, *queries),
    )


async def cleanup_blueprints_status(valid_orgs: list[str]) -> None:
    await mongo.odm.remove(BlueprintStatusModel, query.not_in(BlueprintStatusModel.id.org_id, valid_orgs))


async def cleanup_blueprints_status_of_owner(owner: str, valid_ids: list[str]) -> None:
    await mongo.odm.remove(
        BlueprintStatusModel,
        BlueprintStatusModel.id.org_id == owner,
        query.not_in(BlueprintStatusModel.id.blueprint_id, valid_ids),
    )


async def cleanup_blueprint_status_of_repo(owner: str, repo_name: str, blueprint_id: str) -> None:
    await mongo.odm.remove(
        BlueprintStatusModel,
        BlueprintStatusModel.id.org_id == owner,
        BlueprintStatusModel.id.repo_name == repo_name,
        BlueprintStatusModel.id.blueprint_id == blueprint_id,
    )


async def get_scorecard_results(owner: str) -> list[ScorecardResultModel]:
    return await mongo.odm.find(
        ScorecardResultModel,
        ScorecardResultModel.id.org_id == owner,
        sort=ScorecardResultModel.id.repo_name,
    )


async def find_scorecard_result(owner: str, repo_name: str) -> ScorecardResultModel | None:
    return await mongo.odm.find_one(
        ScorecardResultModel,
        ScorecardResultModel.id.org_id == owner,
        ScorecardResultModel.id.repo_name == repo_name,
    )


async def update_or_create_scorecard_result(
    owner: str,
    repo_name: str,
    date: datetime,
    score: float,
    scorecard_version: str,
    checks: list[dict[str, Any]],
) -> None:
    scorecard_result_model = await find_scorecard_result(owner, repo_name)
    if scorecard_result_model is None:
        scorecard_result_model = ScorecardResultModel(
            id=ScorecardId(org_id=owner, repo_name=repo_name),
        )

    scorecard_result_model.updated_at = date
    scorecard_result_model.score = score
    scorecard_result_model.scorecard_version = scorecard_version
    scorecard_result_model.checks = checks

    await mongo.odm.save(scorecard_result_model)


async def get_scorecard_results_paged(params: dict[str, str]) -> tuple[list[ScorecardResultModel], int]:
    page_index = 1
    page_size = 20
    sort_field_name = "score"
    sort_order = "desc"

    queries: list[QueryExpression] = []

    for k, v in params.items():
        match k:
            case "pageIndex":
                page_index = int(v)
            case "pageSize":
                page_size = int(v)
            case "sortField":
                sort_field_name = v
            case "sortOrder":
                sort_order = v
            case _:
                if v:
                    if k.startswith("id["):
                        match k:
                            case "id[org_id]":
                                queries.append(query.match(ScorecardResultModel.id.org_id, v))
                            case "id[repo_name]":
                                queries.append(query.match(ScorecardResultModel.id.repo_name, v))
                            case _:
                                raise RuntimeError(f"unexpected query field '{k}'")
                    else:
                        queries.append(query.match(ScorecardResultModel.__dict__[k], v))

    if sort_field_name.startswith("id."):
        match sort_field_name:
            case "id.org_id":
                sort_field = ScorecardResultModel.id.org_id
            case "id.repo_name":
                sort_field = ScorecardResultModel.id.repo_name
            case _:
                raise RuntimeError(f"unexpected sort field '{sort_field_name}'")
    else:
        sort_field = ScorecardResultModel.__dict__[sort_field_name]

    sort = query.desc(sort_field) if sort_order == "desc" else query.asc(sort_field)
    skip = (page_index - 1) * page_size
    return (
        await mongo.odm.find(
            ScorecardResultModel,
            *queries,
            skip=skip,
            limit=page_size,
            sort=sort,
        ),
        await mongo.odm.count(ScorecardResultModel, *queries),
    )
