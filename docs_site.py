#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

"""The documentation site, built by Zensical: ``python docs_site.py build|serve|stage [--strict]``.

Zensical runs no hooks, so what the pages need beyond their sources happens before it builds, in the staging directory
``.docs-site/`` (git-ignored), from the sources of the commit being built:

* the pages of docs/, with a link to the playground of the otterdog dashboard below every complete jsonnet example
  (docs_playground.add_playground_links);
* ``.docs-site/zensical.toml``: zensical.toml with the staged pages (docs_dir), the theme override copied next to them
  (custom_dir), the repository root as base path of the snippets (``--8<-- "otterdog/resources/..."``) and what the
  environment sets: ``SITE_URL`` (else ``READTHEDOCS_CANONICAL_URL``) replaces site_url, ``OTTERDOG_URL`` replaces
  extra.otterdog_url (empty: no playground links), ``DOCS_PREVIEW_PR`` builds the preview of that pull request (the
  banner of docs-theme/main.html, kept out of search engines). Zensical keeps every path of a project below the
  directory of its configuration (its cache .docs-site/.cache/ too).

``build`` stages, runs ``zensical build`` into .docs-site/site/ and copies it to site/ (what the docs workflows
publish); ``--strict`` also fails on Zensical's warnings (broken links and anchors). ``serve`` stages for
http://<dev-addr>/, runs ``zensical serve`` and stages again whenever docs/, zensical.toml, docs-theme/ or
docs_playground.py change (only the files that differ are written, so the preview reloads what changed). ``make docs``
and ``make docs-serve*`` run them, the docs workflows run ``build --strict``.

Only the standard library is needed: tests/test_docs_site.py imports this file without the docs group.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import time
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import docs_playground

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Mapping, Sequence

ROOT = Path(__file__).resolve().parent
CONFIG = "zensical.toml"
STAGING = ".docs-site"
THEME = "docs-theme"
SITE = "site"
DOCS = "docs"
# the sources a preview watches (their changes are staged again)
WATCHED = (DOCS, CONFIG, THEME, "docs_playground.py")
POLL_INTERVAL = 1.0
DEV_ADDR = "127.0.0.1:8000"
# the settings docs_site.py sets in the staged configuration, never in zensical.toml
STAGED_KEYS = ("docs_dir", "site_dir", "hooks")
STAGED_THEME = "theme"  # docs-theme/ copied below .docs-site/
_PULL_REQUEST_RE = re.compile(r"[1-9][0-9]{0,9}")

log = logging.getLogger("docs_site")


class SiteError(RuntimeError):
    """The site cannot be staged (an invalid zensical.toml or environment)."""


@dataclass(frozen=True)
class Settings:
    """What the environment sets in the staged configuration (module docstring); None keeps zensical.toml."""

    site_url: str | None = None
    otterdog_url: str | None = None
    preview_pr: str | None = None

    @classmethod
    def from_environment(cls, environ: Mapping[str, str]) -> Settings:
        """SITE_URL (else READTHEDOCS_CANONICAL_URL), OTTERDOG_URL and DOCS_PREVIEW_PR; an empty SITE_URL or
        DOCS_PREVIEW_PR counts as unset, an empty OTTERDOG_URL omits the playground links."""
        return cls(
            site_url=environ.get("SITE_URL") or environ.get("READTHEDOCS_CANONICAL_URL") or None,
            otterdog_url=environ.get("OTTERDOG_URL"),
            preview_pr=environ.get("DOCS_PREVIEW_PR") or None,
        )


def read_config(text: str) -> dict[str, Any]:
    """The ``[project]`` table of zensical.toml."""
    try:
        project = tomllib.loads(text).get("project")
    except tomllib.TOMLDecodeError as exc:
        raise SiteError(f"{CONFIG}: {exc}") from None
    if not isinstance(project, dict):
        raise SiteError(f"{CONFIG}: expected a [project] table")
    return project


def toml_value(value: Any) -> str:
    """``value`` as an inline TOML value (strings, numbers, booleans, arrays and tables: what tomllib reads from
    zensical.toml)."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return repr(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)  # a JSON string is a TOML basic string
    if isinstance(value, list):
        return "[" + ", ".join(toml_value(item) for item in value) + "]"
    if isinstance(value, dict):
        return "{" + ", ".join(f"{toml_value(str(key))} = {toml_value(item)}" for key, item in value.items()) + "}"
    raise SiteError(f"{CONFIG}: cannot write a {type(value).__name__} value")


def staged_config(text: str, root: Path, settings: Settings) -> dict[str, Any]:
    """The ``[project]`` table for Zensical in .docs-site/ (module docstring)."""
    config = read_config(text)
    present = [key for key in STAGED_KEYS if key in config]
    if present:
        raise SiteError(f"{CONFIG}: {', '.join(present)} must not be set (docs_site.py sets the staged ones)")
    theme = config.get("theme") or {}
    if theme.get("custom_dir") != THEME:
        raise SiteError(f"{CONFIG}: theme.custom_dir must be {THEME}")
    extensions = config.get("markdown_extensions") or {}
    snippets = (extensions.get("pymdownx") or {}).get("snippets")
    if not isinstance(snippets, dict) or "base_path" in snippets:
        raise SiteError(f"{CONFIG}: pymdownx.snippets must be enabled without base_path (docs_site.py sets it)")
    snippets["base_path"] = [str(root)]

    extra = dict(config.get("extra") or {})
    if settings.otterdog_url is not None:
        extra["otterdog_url"] = settings.otterdog_url
    extra["otterdog_url"] = str(extra.get("otterdog_url") or "").rstrip("/")
    published = str(config.get("site_url") or "")
    if settings.preview_pr is not None:
        if not _PULL_REQUEST_RE.fullmatch(settings.preview_pr):
            raise SiteError(f"DOCS_PREVIEW_PR: expected the number of a pull request, not {settings.preview_pr!r}")
        extra["preview_pr"] = int(settings.preview_pr)
        extra["published_url"] = published
    return {
        **config,
        "site_url": settings.site_url or published,
        "theme": {**theme, "custom_dir": STAGED_THEME},
        "docs_dir": DOCS,
        "site_dir": SITE,
        "extra": extra,
    }


def render_config(config: Mapping[str, Any]) -> str:
    """The staged zensical.toml of ``config``."""
    lines = [f"# generated by docs_site.py from {CONFIG}", "[project]"]
    return "\n".join([*lines, *(f"{toml_value(key)} = {toml_value(value)}" for key, value in config.items())]) + "\n"


@dataclass
class Staging:
    """The files of the staged site (path below .docs-site/ -> content)."""

    files: dict[str, bytes] = field(default_factory=dict)


def stage(root: Path, settings: Settings) -> Staging:
    """Every file of the staged site (module docstring), in memory."""
    result = Staging()
    config = staged_config((root / CONFIG).read_text(encoding="utf-8"), root, settings)
    result.files[CONFIG] = render_config(config).encode()
    theme = root / THEME
    for path in sorted(theme.rglob("*")):
        if path.is_file():
            result.files[f"{STAGED_THEME}/{path.relative_to(theme).as_posix()}"] = path.read_bytes()

    otterdog_url = config["extra"]["otterdog_url"]
    docs = root / DOCS
    for path in sorted(docs.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        name = f"{DOCS}/{path.relative_to(docs).as_posix()}"
        if path.suffix == ".md" and otterdog_url:
            page = docs_playground.add_playground_links(path.read_text(encoding="utf-8"), otterdog_url)
            result.files[name] = page.encode()
        else:
            result.files[name] = path.read_bytes()
    return result


def write(staging: Path, files: Mapping[str, bytes]) -> list[str]:
    """Make ``staging`` hold exactly ``files`` (the content of the files that differ written, the other staged pages
    and theme files removed; Zensical's cache and site kept); the paths that changed."""
    changed = []
    for name, content in files.items():
        path = staging / name
        if path.is_file() and path.read_bytes() == content:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        changed.append(name)
    for directory in (staging / DOCS, staging / STAGED_THEME):
        for path in sorted(directory.rglob("*"), reverse=True) if directory.is_dir() else []:
            name = path.relative_to(staging).as_posix()
            if path.is_file() and name not in files:
                path.unlink()
                changed.append(name)
            elif path.is_dir() and not any(path.iterdir()):
                path.rmdir()
    return changed


def prepare(root: Path, settings: Settings, staging: Path | None = None) -> Path:
    """Stage the site into ``staging`` (default root/.docs-site); its configuration."""
    staging = staging or root / STAGING
    write(staging, stage(root, settings).files)
    return staging / CONFIG


def zensical(*args: str) -> list[str]:
    """The Zensical command next to this interpreter (the docs group's), else the one on PATH."""
    local = Path(sys.executable).parent / "zensical"
    found = str(local) if local.exists() else shutil.which("zensical")
    if found is None:
        raise SystemExit("zensical is not installed: poetry install --only docs")
    return [found, *args]


def signature(root: Path, watched: Sequence[str] = WATCHED) -> tuple[tuple[str, int, int], ...]:
    """Path, size and mtime of every watched file (a change of any of them changes the signature)."""

    def files() -> Iterator[Path]:
        for name in watched:
            path = root / name
            yield from (item for item in path.rglob("*") if item.is_file()) if path.is_dir() else [path]

    return tuple(
        sorted(
            (item.relative_to(root).as_posix(), stat.st_size, stat.st_mtime_ns)
            for item in files()
            if "__pycache__" not in item.parts and item.exists() and (stat := item.stat())
        )
    )


def serve(root: Path, settings: Settings, dev_addr: str, *, sleep: Callable[[float], None] = time.sleep) -> int:
    """Stage for http://<dev_addr>/, run ``zensical serve`` and stage again on every change of the watched sources
    until it stops."""
    settings = Settings(site_url=f"http://{dev_addr}/", otterdog_url=settings.otterdog_url)
    config = prepare(root, settings)
    process = subprocess.Popen(zensical("serve", "-f", str(config), "-a", dev_addr), cwd=root)  # noqa: S603
    seen = signature(root)
    try:
        while process.poll() is None:
            sleep(POLL_INTERVAL)
            current = signature(root)
            if current != seen:
                seen = current
                try:
                    result = stage(root, settings)
                except SiteError as exc:
                    log.error("%s", exc)
                    continue
                changed = write(root / STAGING, result.files)
                log.info("staged again: %d file(s) changed", len(changed))
    except KeyboardInterrupt:
        process.terminate()
    return process.wait()


def publish(root: Path) -> None:
    """Replace site/ by the site Zensical built in .docs-site/site/."""
    built, site = root / STAGING / SITE, root / SITE
    if site.is_symlink() or site.is_file():
        site.unlink()
    elif site.exists():
        shutil.rmtree(site)
    shutil.copytree(built, site)
    log.info("site/: %d page(s)", sum(1 for _ in site.rglob("*.html")))


def main(argv: Sequence[str] | None = None) -> int:
    """``build``, ``serve`` or ``stage`` (module docstring)."""
    parser = argparse.ArgumentParser(prog="docs_site.py", description=(__doc__ or "").splitlines()[0])
    parser.add_argument("command", choices=("build", "serve", "stage"))
    parser.add_argument("--strict", action="store_true", help="fail on Zensical's warnings (build)")
    parser.add_argument("--dev-addr", default=DEV_ADDR, help=f"address of the preview (serve, default {DEV_ADDR})")
    options = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    settings = Settings.from_environment(os.environ)
    try:
        if options.command == "serve":
            return serve(ROOT, settings, options.dev_addr)
        config = prepare(ROOT, settings)
    except SiteError as exc:
        raise SystemExit(str(exc)) from None
    if options.command == "stage":
        return 0
    command = zensical("build", "--clean", "-f", str(config), *(["--strict"] if options.strict else []))
    code = subprocess.run(command, check=False, cwd=ROOT).returncode  # noqa: S603
    if code == 0:
        publish(ROOT)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
