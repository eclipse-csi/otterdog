#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

"""The theme of the dashboard, like the one of the documentation: its color modes and the hero of its home page."""

from pathlib import Path
from unittest import mock

import pretend
import pytest
from quart import render_template, render_template_string

from otterdog.webapp.db.models import InstallationStatus
from otterdog.webapp.home import routes

_STATIC_DIR = Path(routes.__file__).parents[1] / "static"


@pytest.fixture
def statistics(monkeypatch):
    stats = pretend.stub(
        total_projects=2,
        projects_with_two_factor_auth_enforced=1,
        active_repos=4,
        total_repos=5,
        archived_repos=1,
        repos_with_secret_scanning=1,
        repos_with_secret_scanning_and_protection=1,
        repos_with_dependabot_alerts=1,
        repos_with_dependabot_security_updates=1,
        repos_with_branch_protection=2,
        repos_with_private_vulnerability_reporting=2,
        repos_with_code_scanning=1,
    )
    nothing = mock.AsyncMock(return_value=[])

    monkeypatch.setattr(routes, "get_installations", nothing)
    monkeypatch.setattr(routes, "get_configurations", nothing)
    monkeypatch.setattr(routes, "get_statistics", mock.AsyncMock(return_value=stats))
    monkeypatch.setattr(routes, "get_open_or_incomplete_pull_requests_count", mock.AsyncMock(return_value=0))
    monkeypatch.setattr(routes, "get_merged_pull_requests_count", mock.AsyncMock(return_value=0))
    monkeypatch.setattr(routes, "get_project_navigation", mock.AsyncMock(return_value={}))


async def test_the_home_page_opens_with_the_hero(app, statistics):
    async with app.test_request_context("/index"):
        page = await routes.index()

    documentation_url = app.config["DOCUMENTATION_URL"]
    assert '<section class="otterdog-hero">' in page
    # the logo is decorative, the title has the name of the page as text for screen readers
    assert '<span class="visually-hidden">Otterdog Dashboard</span>' in page
    assert "img/otterdog-logo-white.png" in page
    assert 'href="/playground">Try the playground</a>' in page
    assert 'href="/allprojects">All projects</a>' in page
    assert f'href="{documentation_url}" target="_blank" rel="noopener">' in page
    assert f'href="{documentation_url}userguide/guides/" target="_blank" rel="noopener">' in page


async def test_the_home_page_shows_the_figures_of_the_instance(app, statistics):
    async with app.test_request_context("/index"):
        page = await routes.index()

    assert page.count('class="otterdog-stat otterdog-stat--') == 6
    # the cards of the figures with a page open it
    assert '<a class="otterdog-stat otterdog-stat--purple" href="/admin/organizations">' in page
    assert '<a class="otterdog-stat otterdog-stat--orange" href="/admin/pullrequests#open-prs">' in page
    assert '<a class="otterdog-stat otterdog-stat--green" href="/admin/pullrequests#merged-prs">' in page
    assert "small-box" not in page


async def test_the_home_page_shows_the_shares_as_bars(app, statistics):
    async with app.test_request_context("/index"):
        page = await routes.index()

    # a segmented bar per share rather than a doughnut drawn by Chart.js
    assert page.count('class="otterdog-share__bar"') == 6
    assert "<canvas" not in page
    assert "chart.umd.js" not in page
    assert 'aria-label="Two factor enforcement: Enforced 1, Not required 1"' in page


_SHARE_BAR = (
    '{% from "includes/share-bar.html" import share_bar %}'
    '{{ share_bar("Secret scanning", [{"label": "Protection mode", "count": protection, "status": "good"},'
    ' {"label": "Alert mode", "count": alert, "status": "warning"},'
    ' {"label": "Disabled", "count": disabled, "status": "critical"}]) }}'
)


async def test_a_share_bar_has_a_block_per_part_as_wide_as_its_share(app):
    async with app.app_context():
        bar = await render_template_string(_SHARE_BAR, protection=90, alert=5, disabled=0)

    assert '<div class="otterdog-share__part otterdog-share__part--good" style="flex-grow: 90"' in bar
    assert '<div class="otterdog-share__part otterdog-share__part--warning" style="flex-grow: 5"' in bar
    # a part at zero draws nothing but stays in the legend
    assert 'otterdog-share__part--critical" style' not in bar
    assert "</span>Disabled</li>" in bar
    # the share is printed in the blocks wide enough for it, every share is in the tooltip of its block
    assert 'title="Protection mode: 90 (94.7%)">95%</div>' in bar
    assert 'title="Alert mode: 5 (5.3%)"></div>' in bar


async def test_a_share_bar_of_nothing_is_empty(app):
    async with app.app_context():
        bar = await render_template_string(_SHARE_BAR, protection=0, alert=0, disabled=0)

    assert 'otterdog-share__part--empty" title="No data"' in bar


@pytest.fixture
def projects(monkeypatch):
    installations = [
        pretend.stub(
            project_name="technology.csi", github_id="eclipse-csi", installation_status=InstallationStatus.INSTALLED
        ),
        pretend.stub(
            project_name="ee4j.jakartaee", github_id="jakartaee", installation_status=InstallationStatus.NOT_INSTALLED
        ),
    ]
    settings = {"two_factor_requirement": True, "workflows": {"default_workflow_permissions": "write"}}
    configuration = pretend.stub(github_id="eclipse-csi", config={"settings": settings, "repositories": [{}, {}, {}]})

    monkeypatch.setattr(routes, "get_installations", mock.AsyncMock(return_value=installations))
    monkeypatch.setattr(routes, "get_configurations", mock.AsyncMock(return_value=[configuration]))
    monkeypatch.setattr(routes, "get_project_navigation", mock.AsyncMock(return_value={}))


async def test_a_project_opens_its_page_from_its_card(app, projects):
    async with app.test_request_context("/allprojects"):
        page = await routes.allprojects()

    assert '<a class="otterdog-project__name stretched-link" href="/projects/technology.csi">technology.csi</a>' in page
    # the avatar of the organization, which avatars.githubusercontent.com/<login> does not give
    assert 'src="https://github.com/eclipse-csi.png?size=80"' in page
    assert "Enforced" in page
    # the facts of the configuration in the colors of what they mean
    assert "bg-danger-subtle text-danger-emphasis" in page
    assert '<span class="otterdog-project__count">3</span>' in page


async def test_a_project_not_installed_is_muted_with_its_status(app, projects):
    async with app.test_request_context("/allprojects"):
        page = await routes.allprojects()

    assert page.count('<div class="otterdog-project otterdog-project--inactive">') == 1
    assert '<span class="otterdog-project__name">ee4j.jakartaee</span>' in page
    assert "Not installed" in page


async def test_the_tables_have_the_style_of_the_dashboard(app):
    async with app.app_context():
        table = await render_template_string(
            '{% from "includes/datagrid.html" import paged_table %}{{ paged_table("pulls", ["Status"]) }}'
        )

    assert 'class="table  table-hover align-middle otterdog-table"' in table
    assert "table-bordered" not in table


async def test_a_page_sets_its_color_mode_before_its_styles(app, statistics):
    async with app.test_request_context("/index"):
        page = await routes.index()

    head = page.split("</head>")[0]
    # set before the stylesheets, the page renders in its color mode without a flash of the other one
    assert 'localStorage.getItem("otterdog-color-scheme")' in head
    assert head.index('setAttribute("data-bs-theme"') < head.index('rel="stylesheet"')
    assert "family=Inter" in head


async def test_the_header_toggles_the_color_mode(app, statistics):
    async with app.test_request_context("/index"):
        page = await routes.index()

    assert '<nav class="app-header navbar navbar-expand otterdog-header" data-bs-theme="dark">' in page
    assert "data-otterdog-color-scheme-toggle" in page


async def test_the_fullscreen_pages_show_the_logo_of_the_color_mode(app):
    async with app.test_request_context("/missing"):
        page = await render_template("home/page-404.html")

    head = page.split("</head>")[0]
    assert 'localStorage.getItem("otterdog-color-scheme")' in head
    # the color logo on the light background, the white one on the dark background
    assert 'class="img-fluid otterdog-logo-light"' in page
    assert 'class="img-fluid otterdog-logo-dark"' in page


def test_the_images_of_the_theme_exist():
    for image in ("otterdog-logo.svg", "otterdog-logo-white.png", "otterdog-emblem.png"):
        assert (_STATIC_DIR / "assets" / "img" / image).is_file()
