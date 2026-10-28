#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import json
import re
from pathlib import Path
from unittest import mock

import pretend
import pytest

import otterdog
from otterdog.config import OrganizationConfig, OtterdogConfig
from otterdog.jsonnet import JsonnetConfig
from otterdog.webapp.home import routes

_BASE_TEMPLATE = "https://github.com/example/otterdog-defaults#otterdog-defaults.libsonnet@v1.0.0"
_EXAMPLE_TEMPLATE_DIR = Path(__file__).parents[2] / "otterdog" / "resources" / "defaults"
_TEMPLATE = {
    "files": [
        {
            "filename": "vendor/otterdog-defaults/otterdog-functions.libsonnet",
            "content": "{}",
            "url": "https://github.com/example/otterdog-defaults/blob/v1.0.0/otterdog-functions.libsonnet",
        },
        {
            "filename": "vendor/otterdog-defaults/otterdog-defaults.libsonnet",
            "content": "local functions = import 'otterdog-functions.libsonnet';\n{}",
            "url": "https://github.com/example/otterdog-defaults/blob/v1.0.0/otterdog-defaults.libsonnet",
        },
    ],
    "default_config": "vendor/otterdog-defaults/otterdog-defaults.libsonnet",
    "link": {
        "url": "https://github.com/example/otterdog-defaults/blob/v1.0.0/otterdog-defaults.libsonnet",
        "label": "example/otterdog-defaults/otterdog-defaults.libsonnet@v1.0.0",
    },
}


def _otterdog_config(jsonnet_defaults: dict) -> OtterdogConfig:
    return OtterdogConfig.from_dict({"defaults": {"jsonnet": jsonnet_defaults}, "organizations": []}, False, ".")


async def test_global_playground_uses_the_default_base_template(app, monkeypatch, tmp_path):
    render_playground = mock.AsyncMock(return_value="playground")
    instance_template = mock.AsyncMock(return_value=_TEMPLATE)

    monkeypatch.setattr(routes, "get_temporary_base_directory", lambda: str(tmp_path))

    monkeypatch.setattr(
        routes, "get_otterdog_config", mock.AsyncMock(return_value=_otterdog_config({"base_template": _BASE_TEMPLATE}))
    )
    monkeypatch.setattr(routes, "_instance_template", instance_template)
    monkeypatch.setattr(routes, "_render_playground", render_playground)

    async with app.test_request_context("/playground"):
        result = await routes.global_playground()

    assert result == "playground"
    (org_config,) = instance_template.await_args.args
    assert org_config.base_template == _BASE_TEMPLATE
    assert render_playground.await_args.args == (_TEMPLATE, None)
    assert render_playground.await_args.kwargs["templates"] == [
        {"value": "", "label": "This instance", "selected": True},
        {"value": "example", "label": "Otterdog example", "selected": False},
    ]


async def test_global_playground_uses_the_example_template(app, monkeypatch):
    render_playground = mock.AsyncMock(return_value="playground")
    instance_template = mock.AsyncMock()

    monkeypatch.setattr(
        routes, "get_otterdog_config", mock.AsyncMock(return_value=_otterdog_config({"base_template": _BASE_TEMPLATE}))
    )
    monkeypatch.setattr(routes, "_instance_template", instance_template)
    monkeypatch.setattr(routes, "_render_playground", render_playground)

    async with app.test_request_context("/playground?template=example"):
        result = await routes.global_playground()

    assert result == "playground"
    instance_template.assert_not_awaited()
    template, project_name = render_playground.await_args.args
    assert template == await routes._example_template()
    assert project_name is None
    assert render_playground.await_args.kwargs["templates"] == [
        {"value": "", "label": "This instance", "selected": False},
        {"value": "example", "label": "Otterdog example", "selected": True},
    ]


async def test_global_playground_without_example_template(app, monkeypatch, tmp_path):
    render_playground = mock.AsyncMock(return_value="playground")

    monkeypatch.setattr(routes, "_EXAMPLE_TEMPLATE_DIR", str(tmp_path))
    monkeypatch.setattr(routes, "get_temporary_base_directory", lambda: str(tmp_path))
    monkeypatch.setattr(
        routes, "get_otterdog_config", mock.AsyncMock(return_value=_otterdog_config({"base_template": _BASE_TEMPLATE}))
    )
    monkeypatch.setattr(routes, "_instance_template", mock.AsyncMock(return_value=_TEMPLATE))
    monkeypatch.setattr(routes, "_render_playground", render_playground)

    async with app.test_request_context("/playground?template=example"):
        result = await routes.global_playground()

    assert result == "playground"
    assert render_playground.await_args.args == (_TEMPLATE, None)
    assert render_playground.await_args.kwargs["templates"] is None


async def test_global_playground_without_default_base_template(app, monkeypatch):
    render_playground = mock.AsyncMock()

    monkeypatch.setattr(routes, "get_otterdog_config", mock.AsyncMock(return_value=_otterdog_config({})))
    monkeypatch.setattr(routes, "_render_playground", render_playground)

    async with app.test_request_context("/playground"):
        _, status = await routes.global_playground()

    assert status == 404
    render_playground.assert_not_awaited()


async def test_instance_template_provides_the_files_of_the_default_configuration(monkeypatch, tmp_path):
    monkeypatch.setattr(JsonnetConfig, "init_template", mock.AsyncMock())

    org_config = OrganizationConfig.of(
        "playground", "playground", ".otterdog", _BASE_TEMPLATE, {}, str(tmp_path), str(tmp_path)
    )
    template_dir = tmp_path / "playground" / "vendor" / "otterdog-defaults"
    template_dir.mkdir(parents=True)
    (template_dir / "otterdog-defaults.libsonnet").write_text("{}")

    assert await routes._instance_template(org_config) == {
        "files": [
            {
                "filename": "vendor/otterdog-defaults/otterdog-defaults.libsonnet",
                "content": "{}",
                "url": "https://github.com/example/otterdog-defaults/blob/v1.0.0/otterdog-defaults.libsonnet",
            }
        ],
        "default_config": "vendor/otterdog-defaults/otterdog-defaults.libsonnet",
        "link": {
            "url": "https://github.com/example/otterdog-defaults/blob/v1.0.0/otterdog-defaults.libsonnet",
            "label": "example/otterdog-defaults/otterdog-defaults.libsonnet@v1.0.0",
        },
    }


@pytest.mark.parametrize(("version", "ref"), [("1.6.1", "v1.6.1"), ("1.7.0.dev67", "main")])
async def test_example_template_provides_the_files_of_the_examples(monkeypatch, version, ref):
    monkeypatch.setattr(otterdog, "__version__", version)

    template = await routes._example_template()

    assert template is not None
    assert template["files"] == [
        {
            "filename": f"vendor/otterdog-defaults/{path.name}",
            "content": path.read_text(),
            "url": f"https://github.com/eclipse-csi/otterdog/blob/{ref}/otterdog/resources/defaults/{path.name}",
        }
        for path in sorted(_EXAMPLE_TEMPLATE_DIR.glob("*.libsonnet"))
    ]
    assert template["default_config"] == "vendor/otterdog-defaults/otterdog-defaults.libsonnet"
    assert template["link"] == {
        "url": f"https://github.com/eclipse-csi/otterdog/blob/{ref}/otterdog/resources/defaults/otterdog-defaults.libsonnet",
        "label": f"eclipse-csi/otterdog/otterdog/resources/defaults/otterdog-defaults.libsonnet@{ref}",
    }


async def test_render_playground_provides_the_template(app, monkeypatch):
    render_home_template = mock.AsyncMock(return_value="playground")

    monkeypatch.setattr(routes, "render_home_template", render_home_template)

    async with app.test_request_context("/playground"):
        result = await routes._render_playground(_TEMPLATE, None)

    assert result == "playground"
    context = render_home_template.await_args.kwargs
    assert context["project_name"] is None
    assert context["examples"] == routes._playground_examples()
    assert context["reference"] == routes._playground_reference()
    # the schemas of otterdog, referencing each other by their file name
    assert context["schemas"]["organization.json"]["properties"]["settings"] == {"$ref": "settings.json"}
    assert "types.json" in context["schemas"]
    assert context["default_configuration"] == _TEMPLATE["link"]
    assert context["default_config"] == "vendor/otterdog-defaults/otterdog-defaults.libsonnet"
    assert context["jsonnet_files"] == _TEMPLATE["files"]
    assert context["templates"] is None


def _playground_data(html: str) -> dict:
    match = re.search(r'<script type="application/json" id="playground-data">(.*?)</script>', html, re.DOTALL)
    assert match is not None
    return json.loads(match.group(1))


async def _render_page(app, path: str, **context) -> str:
    from quart import render_template

    async with app.test_request_context(path):
        return await render_template(
            "home/playground.html",
            segments=[segment for segment in path.split("/") if segment],
            projects={},
            version="0.0.0",
            jsonnet_files=_TEMPLATE["files"],
            default_config=_TEMPLATE["default_config"],
            default_configuration=_TEMPLATE["link"],
            examples=routes._playground_examples(),
            documentation_url="https://docs.example.org/",
            **context,
        )


async def test_playground_lists_the_examples_of_the_guides(app):
    pages = routes._playground_examples()

    html = await _render_page(app, "/playground", project_name=None)

    assert len(pages) > 0
    assert 'href="https://github.com/example/otterdog-defaults/blob/v1.0.0/otterdog-defaults.libsonnet"' in html
    assert html.count('data-page="') == sum(len(page["examples"]) for page in pages)
    for page in pages:
        assert f'href="https://docs.example.org/{page["path"]}"' in html

    data = _playground_data(html)
    assert data["examples"] == pages
    assert data["organization"] is None


async def test_playground_shows_the_files_of_the_default_configuration(app):
    html = await _render_page(app, "/playground", project_name=None)

    # the files of the default configuration are listed in a menu, the one imported by the playground first,
    # and shown read-only with a link to their repository
    items = re.findall(r'class="dropdown-item playground-file-item" data-file="([^"]+)"', html)
    assert items == [
        "vendor/otterdog-defaults/otterdog-defaults.libsonnet",
        "vendor/otterdog-defaults/otterdog-functions.libsonnet",
    ]
    for file in _TEMPLATE["files"]:
        assert f'aria-label="{file["filename"]} (read-only)"' in html
        assert f'href="{file["url"]}"' in html
    assert 'data-file="playground.jsonnet"' in html

    data = _playground_data(html)
    assert data["templateFiles"] == _TEMPLATE["files"]
    assert data["defaultConfig"] == _TEMPLATE["default_config"]
    # the evaluator loads its own runtime, the page passes no url to it
    assert "wasm" not in data


async def test_playground_offers_the_choice_of_the_template(app):
    html = await _render_page(
        app,
        "/playground",
        project_name=None,
        templates=[
            {"value": "", "label": "This instance", "selected": False},
            {"value": "example", "label": "Otterdog example", "selected": True},
        ],
    )

    assert 'id="playground-template"' in html
    assert '<option value="">This instance</option>' in html
    assert '<option value="example" selected>Otterdog example</option>' in html
    assert 'id="playground-changes-tab"' not in html


async def test_playground_examples_can_be_collapsed(app):
    html = await _render_page(app, "/playground", project_name=None)

    assert 'id="playground-examples-toggle"' in html
    assert 'aria-controls="playground-examples-body"' in html
    assert 'id="playground-examples-body"' in html


async def test_playground_without_choice_of_the_template(app):
    html = await _render_page(app, "/playground", project_name=None)

    assert 'id="playground-template"' not in html
    assert "Default configuration:" in html


@pytest.mark.parametrize(
    ("jsonnet", "branch", "edit_url"),
    [
        (
            "orgs.newOrg('my-project', 'my-org')\n",
            "main",
            "https://github.com/my-org/.otterdog/edit/main/otterdog/my-org.jsonnet",
        ),
        # fetched before the default branch was stored, the playground falls back to the file
        ("orgs.newOrg('my-project', 'my-org')\n", None, None),
        (None, None, None),
    ],
)
async def test_project_playground_starts_with_the_configuration_of_the_organization(
    app, monkeypatch, tmp_path, jsonnet, branch, edit_url
):
    render_playground = mock.AsyncMock(return_value="playground")
    configuration = pretend.stub(github_id="my-org", sha="abc123", jsonnet=jsonnet, branch=branch)

    monkeypatch.setattr(routes, "get_temporary_base_directory", lambda: str(tmp_path))
    monkeypatch.setattr(routes, "get_installation_by_project_name", mock.AsyncMock(return_value=pretend.stub()))
    monkeypatch.setattr(
        routes, "get_organization_config", mock.AsyncMock(return_value=pretend.stub(config_repo=".otterdog"))
    )
    monkeypatch.setattr(routes, "get_configuration_by_project_name", mock.AsyncMock(return_value=configuration))
    monkeypatch.setattr(routes, "_instance_template", mock.AsyncMock(return_value=_TEMPLATE))
    monkeypatch.setattr(routes, "_render_playground", render_playground)

    async with app.test_request_context("/projects/my-project/playground"):
        result = await routes.playground("my-project")

    assert result == "playground"
    template, project_name, organization = render_playground.await_args.args
    assert template == _TEMPLATE
    assert project_name == "my-project"
    if jsonnet is None:
        assert organization is None
    else:
        assert organization == {
            "name": "my-project",
            "jsonnet": jsonnet,
            "url": "https://github.com/my-org/.otterdog/blob/HEAD/otterdog/my-org.jsonnet",
            "edit_url": edit_url,
        }


async def test_playground_lists_the_configuration_of_the_organization(app):
    organization = {
        "name": "my-project",
        "jsonnet": "orgs.newOrg('my-project', 'my-org')\n",
        "url": "https://github.com/my-org/.otterdog/blob/HEAD/otterdog/my-org.jsonnet",
    }

    html = await _render_page(
        app, "/projects/my-project/playground", project_name="my-project", organization=organization
    )

    assert 'data-organization="true"' in html
    assert 'href="https://github.com/my-org/.otterdog/blob/HEAD/otterdog/my-org.jsonnet"' in html
    assert "orgs.newOrg(\\u0027my-project\\u0027, \\u0027my-org\\u0027)" in html
    assert _playground_data(html)["organization"] == organization
    # the changes are shown compared to the current configuration of the organization
    assert 'id="playground-changes-tab"' in html
    assert 'id="playground-template"' not in html


@pytest.mark.parametrize("edit_url", ["https://github.com/my-org/.otterdog/edit/main/otterdog/my-org.jsonnet", None])
async def test_playground_proposes_the_changes_on_github(app, edit_url):
    organization = {
        "name": "my-project",
        "jsonnet": "orgs.newOrg('my-project', 'my-org')\n",
        "url": "https://github.com/my-org/.otterdog/blob/HEAD/otterdog/my-org.jsonnet",
        "edit_url": edit_url,
    }

    html = await _render_page(
        app, "/projects/my-project/playground", project_name="my-project", organization=organization
    )

    # the pull request is created from the account of the user, in the editor of GitHub
    assert 'id="playground-propose"' in html
    assert 'id="playground-propose-modal"' in html
    assert f'id="playground-propose-open" href="{edit_url or organization["url"]}"' in html
    # without the branch, the file is opened and edited from there
    assert ("pencil" in html) == (edit_url is None)


async def test_global_playground_does_not_propose_changes(app):
    html = await _render_page(app, "/playground", project_name=None)

    assert 'id="playground-propose"' not in html
    assert 'id="playground-propose-modal"' not in html


async def test_configurations_of_the_projects_using_the_default_base_template(app, monkeypatch):
    installations = [
        pretend.stub(project_name="beta", github_id="beta-org", base_template=_BASE_TEMPLATE),
        pretend.stub(project_name="alpha", github_id="alpha-org", base_template=_BASE_TEMPLATE),
        pretend.stub(project_name="other", github_id="other-org", base_template="https://github.com/other/template"),
        pretend.stub(project_name="new", github_id="new-org", base_template=_BASE_TEMPLATE),
    ]
    sources = mock.AsyncMock(return_value={"alpha-org": "orgs.newOrg('alpha', 'alpha-org')", "beta-org": None})
    monkeypatch.setattr(
        routes, "get_otterdog_config", mock.AsyncMock(return_value=_otterdog_config({"base_template": _BASE_TEMPLATE}))
    )
    monkeypatch.setattr(routes, "get_active_installations", mock.AsyncMock(return_value=installations))
    monkeypatch.setattr(routes, "get_configuration_sources", sources)

    async with app.test_request_context("/admin/template-impact/configurations"):
        result = await routes.template_impact_configurations()

    # only the sources of the projects using the default base template are loaded
    (github_ids,) = sources.await_args.args
    assert sorted(github_ids) == ["alpha-org", "beta-org", "new-org"]

    # sorted by project, the configurations not fetched with their source yet being null
    assert result == {
        "projects": [
            {"name": "alpha", "jsonnet": "orgs.newOrg('alpha', 'alpha-org')"},
            {"name": "beta", "jsonnet": None},
            {"name": "new", "jsonnet": None},
        ]
    }


async def test_no_configurations_without_default_base_template(app, monkeypatch):
    monkeypatch.setattr(routes, "get_otterdog_config", mock.AsyncMock(return_value=_otterdog_config({})))

    async with app.test_request_context("/admin/template-impact/configurations"):
        assert await routes.template_impact_configurations() == {"projects": []}


async def test_the_impact_of_the_template_is_evaluated_with_the_default_base_template(app, monkeypatch, tmp_path):
    render_home_template = mock.AsyncMock(return_value="template impact")
    instance_template = mock.AsyncMock(return_value=_TEMPLATE)
    monkeypatch.setattr(routes, "get_temporary_base_directory", lambda: str(tmp_path))
    monkeypatch.setattr(
        routes, "get_otterdog_config", mock.AsyncMock(return_value=_otterdog_config({"base_template": _BASE_TEMPLATE}))
    )
    monkeypatch.setattr(routes, "_instance_template", instance_template)
    monkeypatch.setattr(routes, "render_home_template", render_home_template)

    async with app.test_request_context("/admin/template-impact"):
        assert await routes.template_impact() == "template impact"

    (org_config,) = instance_template.await_args.args
    assert org_config.base_template == _BASE_TEMPLATE
    assert render_home_template.await_args.args == ("template-impact.html",)
    assert render_home_template.await_args.kwargs == {
        "jsonnet_files": _TEMPLATE["files"],
        "default_config": _TEMPLATE["default_config"],
        "default_configuration": _TEMPLATE["link"],
    }


async def test_no_impact_of_the_template_without_default_base_template(app, monkeypatch):
    monkeypatch.setattr(routes, "get_otterdog_config", mock.AsyncMock(return_value=_otterdog_config({})))

    async with app.test_request_context("/admin/template-impact"):
        _, status = await routes.template_impact()

    assert status == 404
