#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import json
import re
import tomllib
from pathlib import Path

import pytest

import docs_site

_ROOT_DIR = Path(__file__).parent.parent
_CONFIG = (_ROOT_DIR / "zensical.toml").read_text()


def _nav_pages(entries: list) -> list[str]:
    pages = []
    for entry in entries:
        target = next(iter(entry.values())) if isinstance(entry, dict) else entry
        pages += _nav_pages(target) if isinstance(target, list) else [target]
    return pages


def test_staged_config():
    config = docs_site.staged_config(_CONFIG, _ROOT_DIR, docs_site.Settings())

    assert config["docs_dir"] == "docs"
    assert config["site_dir"] == "site"
    assert config["theme"]["custom_dir"] == "theme"
    assert config["site_url"] == "https://csi.eclipse.dev/otterdog/"
    assert config["markdown_extensions"]["pymdownx"]["snippets"]["base_path"] == [str(_ROOT_DIR)]
    assert config["extra"]["otterdog_url"] == "https://otterdog.eclipse.org"
    assert "preview_pr" not in config["extra"]


def test_staged_config_is_valid_toml():
    config = docs_site.staged_config(_CONFIG, _ROOT_DIR, docs_site.Settings())

    assert tomllib.loads(docs_site.render_config(config))["project"] == config


@pytest.mark.parametrize(
    ("environ", "site_url"),
    [
        ({}, "https://csi.eclipse.dev/otterdog/"),
        (
            {"READTHEDOCS_CANONICAL_URL": "https://otterdog.readthedocs.io/en/latest/"},
            "https://otterdog.readthedocs.io/en/latest/",
        ),
        (
            {"READTHEDOCS_CANONICAL_URL": "https://rtd.example/", "SITE_URL": "https://preview.example/pr-1/"},
            "https://preview.example/pr-1/",
        ),
        ({"SITE_URL": ""}, "https://csi.eclipse.dev/otterdog/"),
    ],
)
def test_site_url_from_environment(environ, site_url):
    settings = docs_site.Settings.from_environment(environ)

    assert docs_site.staged_config(_CONFIG, _ROOT_DIR, settings)["site_url"] == site_url


@pytest.mark.parametrize(
    ("value", "expected"), [("https://otterdog.example.org/", "https://otterdog.example.org"), ("", "")]
)
def test_otterdog_url_from_environment(value, expected):
    settings = docs_site.Settings.from_environment({"OTTERDOG_URL": value})

    assert docs_site.staged_config(_CONFIG, _ROOT_DIR, settings)["extra"]["otterdog_url"] == expected


def test_preview_of_a_pull_request():
    settings = docs_site.Settings.from_environment({"DOCS_PREVIEW_PR": "123", "SITE_URL": "https://preview.example/"})

    config = docs_site.staged_config(_CONFIG, _ROOT_DIR, settings)

    assert config["extra"]["preview_pr"] == 123
    assert config["extra"]["published_url"] == "https://csi.eclipse.dev/otterdog/"
    assert config["site_url"] == "https://preview.example/"


@pytest.mark.parametrize("value", ["0", "-1", "12a", "1; rm -rf /", "1\n2", "\uff11\uff12"])
def test_preview_requires_the_number_of_a_pull_request(value):
    settings = docs_site.Settings(preview_pr=value)

    with pytest.raises(docs_site.SiteError, match="DOCS_PREVIEW_PR"):
        docs_site.staged_config(_CONFIG, _ROOT_DIR, settings)


def test_the_address_of_the_preview_server():
    settings = docs_site.Settings(site_url="http://127.0.0.1:8001/", dev_addr="127.0.0.1:8001")

    config = docs_site.staged_config(_CONFIG, _ROOT_DIR, settings)

    assert config["dev_addr"] == "127.0.0.1:8001"
    assert config["site_url"] == "http://127.0.0.1:8001/"
    assert "dev_addr" not in docs_site.staged_config(_CONFIG, _ROOT_DIR, docs_site.Settings())


@pytest.mark.parametrize("value", ["127.0.0.1", "-a:8000", "localhost:8000 --strict", "host:port", ":8000"])
def test_the_address_of_the_preview_server_is_host_and_port(value):
    settings = docs_site.Settings(dev_addr=value)

    with pytest.raises(docs_site.SiteError, match="--dev-addr"):
        docs_site.staged_config(_CONFIG, _ROOT_DIR, settings)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda text: text.replace("[project]\n", '[project]\ndocs_dir = "elsewhere"\n', 1), "docs_dir"),
        (lambda text: text.replace('custom_dir = "docs-theme"', 'custom_dir = "overrides"'), "custom_dir"),
        (
            lambda text: text.replace("pymdownx.snippets.check_paths = true", 'pymdownx.snippets.base_path = ["."]'),
            "snippets",
        ),
        (lambda text: text.replace("pymdownx.snippets.check_paths = true\n", ""), "snippets"),
    ],
)
def test_settings_set_by_the_staging_are_refused(change, message):
    text, settings = change(_CONFIG), docs_site.Settings()

    with pytest.raises(docs_site.SiteError, match=message):
        docs_site.staged_config(text, _ROOT_DIR, settings)


def test_stage_adds_playground_links():
    files = docs_site.stage(_ROOT_DIR, docs_site.Settings(otterdog_url="https://otterdog.example.org")).files

    assert (
        "Open in the Playground](https://otterdog.example.org/playground?"
        in files["docs/userguide/guides/webhooks.md"].decode()
    )
    logo = "docs/assets/images/otterdog-emblem.png"
    assert files[logo] == (_ROOT_DIR / logo).read_bytes()
    assert files["theme/main.html"] == (_ROOT_DIR / "docs-theme" / "main.html").read_bytes()
    assert tomllib.loads(files["zensical.toml"].decode())["project"]["docs_dir"] == "docs"


def test_stage_without_otterdog_url_keeps_the_pages():
    files = docs_site.stage(_ROOT_DIR, docs_site.Settings(otterdog_url="")).files

    for page in (_ROOT_DIR / "docs").rglob("*.md"):
        assert files[f"docs/{page.relative_to(_ROOT_DIR / 'docs').as_posix()}"] == page.read_bytes()


def test_write_keeps_the_staging_in_sync(tmp_path):
    assert sorted(docs_site.write(tmp_path, {"docs/a.md": b"a", "docs/sub/b.md": b"b", "zensical.toml": b"c"})) == [
        "docs/a.md",
        "docs/sub/b.md",
        "zensical.toml",
    ]
    (tmp_path / ".cache").mkdir()

    assert docs_site.write(tmp_path, {"docs/a.md": b"a2", "zensical.toml": b"c"}) == ["docs/a.md", "docs/sub/b.md"]
    assert not (tmp_path / "docs" / "sub").exists()
    assert (tmp_path / ".cache").is_dir()
    assert docs_site.write(tmp_path, {"docs/a.md": b"a2", "zensical.toml": b"c"}) == []


def test_every_page_of_the_nav_exists():
    nav = tomllib.loads(_CONFIG)["project"]["nav"]

    missing = [page for page in _nav_pages(nav) if not (_ROOT_DIR / "docs" / page).is_file()]

    assert missing == []


def test_hero_buttons_open_pages_of_the_nav():
    pages = set(_nav_pages(tomllib.loads(_CONFIG)["project"]["nav"]))
    hero = (_ROOT_DIR / "docs-theme" / "main.html").read_text()

    links = re.findall(r"""href="\{\{ '([^']*)' \| url \}\}\"""", hero)

    assert links
    # a page of the nav is served at <page>/, an index page at its directory
    assert [link for link in links if f"{link}index.md" not in pages and f"{link.rstrip('/')}.md" not in pages] == []


def test_the_images_of_the_theme_exist():
    theme = tomllib.loads(_CONFIG)["project"]["theme"]
    main = (_ROOT_DIR / "docs-theme" / "main.html").read_text()

    # the logo and the favicon, the logo of the hero and the social card, all served from docs/
    images = [
        theme["logo"],
        theme["favicon"],
        *re.findall(r"""src="\{\{ '([^']*)' \| url \}\}\"""", main),
        *re.findall(r"""\{\{ config\.site_url \}\}([^"]*)""", main),
    ]

    assert len(images) == 4
    assert [image for image in images if not (_ROOT_DIR / "docs" / image).is_file()] == []


def _anchors(page: Path) -> set[str]:
    """The anchors of the headings of a page (the default slugify of the toc extension, as docs_playground)."""
    import docs_playground

    headings = re.findall(r"^#{1,6} +(\S.*)$", page.read_text(), re.MULTILINE)
    return {docs_playground._slugify(docs_playground._plain_text(heading)) for heading in headings}


def _documentation_links() -> list[tuple[str, str]]:
    """The links of the webapp to the documentation: the catalogs of the Playground, its scripts and the templates."""
    home = _ROOT_DIR / "otterdog" / "webapp" / "home"
    examples = json.loads((home / "playground-examples.json").read_text())
    reference = json.loads((home / "playground-reference.json").read_text())
    links = [("playground-examples.json", page["path"]) for page in examples["pages"]]
    links += [
        ("playground-examples.json", f"{page['path']}#{example['anchor']}")
        for page in examples["pages"]
        for example in page["examples"]
    ]
    links += [("playground-reference.json", entry["url"]) for entry in reference["objects"].values()]
    webapp = _ROOT_DIR / "otterdog" / "webapp"
    sources = [*(webapp / "templates").rglob("*.html"), *(webapp / "static" / "src").rglob("*.js")]
    for source in sources:
        if not source.name.endswith(".test.js"):
            for link in re.findall(
                r"(?:userguide|reference|operating_otterdog|developing_otterdog)/[\w./#-]*", source.read_text()
            ):
                links.append((source.relative_to(_ROOT_DIR).as_posix(), link))
    return links


def test_the_links_of_the_webapp_to_the_documentation_exist():
    docs = _ROOT_DIR / "docs"
    broken = []
    for origin, link in _documentation_links():
        path, _, anchor = link.partition("#")
        # a page is served at <page>/, an index page at its directory
        page = next(
            (
                candidate
                for candidate in (docs / path / "index.md", docs / f"{path.rstrip('/')}.md")
                if candidate.is_file()
            ),
            None,
        )
        if page is None or (anchor and anchor not in _anchors(page)):
            broken.append(f"{origin}: {link}")

    assert len(_documentation_links()) > 100
    assert broken == []


def test_the_requirements_of_the_docs_group():
    lock = tomllib.loads((_ROOT_DIR / "poetry.lock").read_text())
    docs = {package["name"]: package for package in lock["package"] if "docs" in package.get("groups", [])}

    text = docs_site.requirements((_ROOT_DIR / "poetry.lock").read_text())

    entries = [entry.strip() for entry in text.replace("\\\n", " ").splitlines() if not entry.startswith("#")]
    pinned = {entry.split()[0].split("==")[0]: entry for entry in entries}
    assert set(pinned) == set(docs)
    assert {"zensical", "pymdown-extensions"} <= set(pinned)
    for name, entry in pinned.items():
        assert entry.startswith(f"{name}=={docs[name]['version']}")
        assert re.findall(r"--hash=(\S+)", entry) == [file["hash"] for file in docs[name]["files"]]


def test_the_requirements_keep_the_markers_of_the_group():
    lock = """
[[package]]
name = "colorama"
version = "0.4.6"
groups = ["main", "docs"]
markers = {main = "sys_platform == \\"win32\\"", docs = "platform_system == \\"Windows\\""}
files = [{file = "colorama-0.4.6-py2.py3-none-any.whl", hash = "sha256:aaaa"}]

[[package]]
name = "quart"
version = "0.20.0"
groups = ["app"]
files = [{file = "quart-0.20.0-py3-none-any.whl", hash = "sha256:bbbb"}]
"""

    assert docs_site.requirements(lock).splitlines()[1:] == [
        'colorama==0.4.6 ; platform_system == "Windows" \\',
        "    --hash=sha256:aaaa",
    ]


@pytest.mark.parametrize(
    "lock",
    [
        '[[package]]\nname = "zensical"\nversion = "1"\ngroups = ["docs"]\nfiles = []\n',
        '[[package]]\nname = "quart"\nversion = "1"\ngroups = ["app"]\nfiles = [{file = "q.whl", hash = "sha256:b"}]\n',
    ],
)
def test_the_requirements_need_the_hashes_of_the_docs_group(lock):
    with pytest.raises(docs_site.SiteError, match=r"poetry\.lock"):
        docs_site.requirements(lock)
