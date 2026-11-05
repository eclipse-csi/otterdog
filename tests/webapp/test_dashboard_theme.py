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
from quart import render_template

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
