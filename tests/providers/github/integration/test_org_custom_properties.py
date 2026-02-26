#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from otterdog.models.custom_property import CustomProperty

from .conftest import GitHubProviderTestKit
from .helpers.model import ModelForContext

# Constants
ORG_ID = "test-org"
REPO_NAME = "test-repo"


async def generate_patch_and_run_it(
    github: GitHubProviderTestKit,
    *,
    old: CustomProperty | None,
    new: CustomProperty | None,
):
    """Generate and apply a LivePatch in one call."""
    model = ModelForContext(ORG_ID, repo_name=REPO_NAME)

    patch = model.generate_live_patch(old=old, new=new)
    await patch.apply(ORG_ID, github.provider)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# CRUD operations for CustomProperty
# ---------------------------------------------------------------------------


async def test_create(github: GitHubProviderTestKit):
    """Creates an org custom property through a generated live patch."""
    github.http.expect(
        "PUT",
        f"/orgs/{ORG_ID}/properties/schema/language",
        request_json={
            "value_type": "single_select",
            "required": True,
            "default_value": "Python",
            "description": "Primary language",
            "allowed_values": ["Python", "Java"],
        },
        response_json={},
    )

    await generate_patch_and_run_it(
        github,
        old=None,
        new=CustomProperty(
            name="language",
            value_type="single_select",
            required=True,
            default_value="Python",
            description="Primary language",
            allowed_values=["Python", "Java"],
        ),
    )


async def test_read(github: GitHubProviderTestKit):
    """Reads org custom properties from provider payloads."""
    github.http.expect(
        "GET",
        f"/orgs/{ORG_ID}/properties/schema",
        response_json=[
            {
                "property_name": "language",
                "value_type": "single_select",
                "required": True,
                "default_value": "Python",
                "description": "Primary language",
                "allowed_values": ["Python", "Java"],
            },
            {
                "property_name": "cost_center",
                "value_type": "string",
                "required": False,
                "default_value": "",
                "description": None,
            },
        ],
    )

    data = await github.provider.get_org_custom_properties(ORG_ID)
    properties = [CustomProperty.from_provider_data(ORG_ID, d) for d in data]

    assert properties == [
        CustomProperty(
            name="language",
            value_type="single_select",
            required=True,
            default_value="Python",
            description="Primary language",
            allowed_values=["Python", "Java"],
        ),
        CustomProperty(
            name="cost_center",
            value_type="string",
            required=False,
            default_value="",
            description=None,
            allowed_values=[],
        ),
    ]


async def test_update(github: GitHubProviderTestKit):
    """Updates an org custom property through a generated live patch."""
    github.http.expect(
        "PUT",
        f"/orgs/{ORG_ID}/properties/schema/language",
        request_json={
            "value_type": "single_select",
            "required": True,
            "default_value": "Java",
            "description": "Primary language",
            "allowed_values": ["Python", "Java"],
        },
        response_json={},
    )

    await generate_patch_and_run_it(
        github,
        old=CustomProperty(
            name="language",
            value_type="single_select",
            required=True,
            default_value="Python",
            description="Primary language",
            allowed_values=["Python", "Java"],
        ),
        new=CustomProperty(
            name="language",
            value_type="single_select",
            required=True,
            default_value="Java",
            description="Primary language",
            allowed_values=["Python", "Java"],
        ),
    )


async def test_delete(github: GitHubProviderTestKit):
    """Deletes an org custom property through a generated live patch."""
    github.http.expect(
        "DELETE",
        f"/orgs/{ORG_ID}/properties/schema/language",
        response_status=204,
    )

    await generate_patch_and_run_it(
        github,
        old=CustomProperty(
            name="language",
            value_type="single_select",
            required=True,
            default_value="Python",
            description="Primary language",
            allowed_values=["Python", "Java"],
        ),
        new=None,
    )
