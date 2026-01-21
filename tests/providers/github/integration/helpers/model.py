#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from otterdog.models import LivePatch, LivePatchContext, ModelObject
from otterdog.models.environment import Environment
from otterdog.models.organization_secret import OrganizationSecret
from otterdog.models.organization_settings import OrganizationSettings
from otterdog.models.organization_variable import OrganizationVariable
from otterdog.models.repo_secret import RepositorySecret
from otterdog.models.repo_variable import RepositoryVariable
from otterdog.models.repository import Repository


def determine_model_object(
    a: ModelObject | None,
    b: ModelObject | None,
) -> type[ModelObject]:
    """
    Determine the model object type from the given objects.

    At least one of a or b must be not None.
    If both are provided, they must be of the same type.
    """
    if a and b:
        assert type(a) == type(b), "Both objects must be of the same type"  # noqa: E721
        return type(a)
    elif a:
        return type(a)
    elif b:
        return type(b)
    else:
        raise ValueError("At least one of a or b must be provided")


class ModelForContext:
    """A model with some common objects for tests."""

    def __init__(
        self,
        org_id: str,
        *,
        repo_name: str | None = None,
        env_name: str | None = None,
    ):
        self.org = OrganizationSettings.from_model_data({"name": org_id})

        if repo_name:
            self.repository = Repository.from_model_data({"name": repo_name})
        if env_name:
            self.environment = Environment.from_model_data({"name": env_name})

        self.live_patch_context = LivePatchContext(
            org_id=org_id,
            repo_filter="",
            update_webhooks=False,
            update_secrets=True,
            update_filter="*",
            current_org_settings=self.org,
            expected_org_settings=self.org,
        )

    def generate_live_patch(
        self,
        old: ModelObject | None,
        new: ModelObject | None,
    ) -> LivePatch:
        """Generate exactly one LivePatch for a given model class.

        Collects the patch by calling model_cls.generate_live_patch and ensures exactly one is produced.

        !old & new => Create
        old & new => Update
        old & !new => Delete
        """
        model_cls = determine_model_object(old, new)

        patches: list[LivePatch] = []
        model_cls.generate_live_patch(
            expected_object=new,
            current_object=old,
            parent_object=self.get_parent_object(old, new),
            context=self.live_patch_context,
            handler=lambda p: patches.append(p),  # pyright: ignore[reportArgumentType]
        )
        assert len(patches) == 1, f"Expected exactly one patch, got {len(patches)}"
        return patches[0]

    def get_parent_object(self, old: ModelObject | None, new: ModelObject | None) -> ModelObject | None:
        """
        Based on provided old/new objects and test context, return the correct parent object.
        Objects do not store their parents directly, so we need to reconstruct them here.
        """

        model_cls = determine_model_object(old, new)
        if model_cls in {RepositorySecret, RepositoryVariable}:
            return self.repository
        if model_cls in {OrganizationSecret, OrganizationVariable}:
            return None  # Organization-level, no parent object
        raise ValueError(f"Unknown model class for parent: {model_cls}")
