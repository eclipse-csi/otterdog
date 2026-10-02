#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from unittest.mock import AsyncMock, patch

from otterdog.webapp.blueprints import read_blueprint
from otterdog.webapp.db.models import BlueprintId, BlueprintModel
from otterdog.webapp.db.service import update_or_create_blueprint

BLUEPRINT_PATH = "https://github.com/my-org/.eclipsefdn/blob/main/otterdog/blueprints/codeql.yml"


def _blueprint(description: str = "old description", content: str = "old content"):
    return read_blueprint(
        BLUEPRINT_PATH,
        {
            "id": "codeql",
            "name": "CodeQL",
            "description": description,
            "type": "required_file",
            "config": {"files": [{"path": ".github/workflows/codeql.yml", "content": content, "strict": True}]},
        },
    )


def _stored_model(blueprint, recheck_needed: bool = False) -> BlueprintModel:
    return BlueprintModel(
        id=BlueprintId(org_id="my-org", blueprint_type=blueprint.type.value, blueprint_id=blueprint.id),
        path=blueprint.path,
        name=blueprint.name,
        description=blueprint.description,
        config=blueprint.config,
        recheck_needed=recheck_needed,
    )


async def _update(stored: BlueprintModel | None, blueprint) -> tuple[bool, BlueprintModel]:
    with (
        patch("otterdog.webapp.db.service.find_blueprint", AsyncMock(return_value=stored)),
        patch("otterdog.webapp.db.service.save_blueprint", AsyncMock()) as save,
    ):
        recheck = await update_or_create_blueprint("my-org", blueprint)

    save.assert_awaited_once()
    return recheck, save.await_args.args[0]


async def test_new_blueprint_needs_recheck():
    recheck, saved = await _update(None, _blueprint())

    assert recheck is True
    assert saved.recheck_needed is True
    assert saved.id.blueprint_type == "required_file"


async def test_unchanged_blueprint_does_not_need_recheck():
    recheck, saved = await _update(_stored_model(_blueprint()), _blueprint())

    assert recheck is False
    assert saved.recheck_needed is False


async def test_changing_description_and_content_together_stores_both():
    # regression: a short-circuiting `or` stored the description but dropped the content
    stored = _stored_model(_blueprint())
    updated = _blueprint(description="new description", content="new content")

    recheck, saved = await _update(stored, updated)

    assert recheck is True
    assert saved.description == "new description"
    assert saved.config == updated.config


async def test_pending_recheck_survives_unrelated_update():
    # regression: a later push that left this blueprint unchanged reset a pending recheck
    stored = _stored_model(_blueprint(), recheck_needed=True)

    recheck, saved = await _update(stored, _blueprint())

    assert recheck is True
    assert saved.recheck_needed is True


async def test_changing_type_replaces_model():
    # the type is part of the primary key, so the old model is deleted and a new one created
    stored = _stored_model(_blueprint())
    changed_type = read_blueprint(
        BLUEPRINT_PATH,
        {
            "id": "codeql",
            "name": "CodeQL",
            "type": "scorecard_integration",
            "config": {"workflow_content": "name: scorecard"},
        },
    )

    with (
        patch("otterdog.webapp.db.service.find_blueprint", AsyncMock(return_value=stored)),
        patch("otterdog.webapp.db.service.save_blueprint", AsyncMock()) as save,
        patch("otterdog.webapp.db.service.mongo") as mongo,
    ):
        mongo.odm.delete = AsyncMock()
        recheck = await update_or_create_blueprint("my-org", changed_type)

    mongo.odm.delete.assert_awaited_once_with(stored)
    saved = save.await_args.args[0]
    assert recheck is True
    assert saved.id.blueprint_type == "scorecard_integration"
    assert saved.id.blueprint_id == "codeql"
    assert saved.recheck_needed is True
