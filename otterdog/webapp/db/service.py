#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

from typing import Sequence, cast

from quart import Quart
from sqlalchemy import desc, func, select

from otterdog.webapp import db
from otterdog.webapp.utils import get_otterdog_config, get_rest_api_for_app

from .models import DBTask, Organization


async def fill_organization_table(app: Quart):
    async with app.app_context():
        app.logger.info("filling database with app installations")
        rest_api = get_rest_api_for_app()
        otterdog_config = get_otterdog_config()
        for app_installation in await rest_api.app.get_app_installations():
            installation_id = app_installation["id"]
            github_id = app_installation["account"]["login"]
            project_name = otterdog_config.get_project_name(github_id) or github_id

            organization = db.session.get(Organization, installation_id)  # type: ignore
            if organization:
                organization.project_name = project_name
            else:
                organization = Organization(
                    installation_id=installation_id, github_id=github_id, project_name=project_name
                )
                db.session.add(organization)  # type: ignore

            db.session.commit()  # type: ignore


def get_or_create(session, model, defaults=None, **kwargs):
    instance = session.query(model).filter_by(**kwargs).one_or_none()
    if instance:
        return instance, False
    else:
        kwargs |= defaults or {}
        instance = model(**kwargs)
        try:
            session.add(instance)
            session.commit()
        except Exception:
            # The actual exception depends on the specific database, so we catch all exceptions.
            # This is similar to the official documentation:
            # https://docs.sqlalchemy.org/en/latest/orm/session_transaction.html
            session.rollback()
            instance = session.query(model).filter_by(**kwargs).one()
            return instance, False
        else:
            return instance, True


def get_organization_count() -> int:
    return cast(
        int, db.session.execute(db.session.query(func.count(Organization.installation_id))).scalar()  # type: ignore
    )


def get_organizations() -> Sequence[Organization]:
    return db.session.execute(select(Organization)).scalars().all()  # type: ignore


def get_tasks(limit: int) -> Sequence[DBTask]:
    return (
        db.session.execute(select(DBTask).order_by(desc(DBTask.created_at))).scalars().fetchmany(limit)  # type: ignore
    )
