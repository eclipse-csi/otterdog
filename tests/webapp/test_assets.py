#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import hashlib

from quart import render_template_string


async def _render_asset(app, file_path: str) -> str:
    async with app.app_context():
        return await render_template_string("{{ asset(file_path) }}", file_path=file_path)


async def test_asset_versions_files_outside_the_manifest(app, tmp_path):
    content = b"console.log('vendor');"
    (tmp_path / "vendor").mkdir()
    (tmp_path / "vendor" / "lib.js").write_bytes(content)
    app.static_folder = str(tmp_path)

    expected_hash = hashlib.sha256(content).hexdigest()[:8]
    assert await _render_asset(app, "vendor/lib.js") == f"/assets/vendor/lib.js?v={expected_hash}"


async def test_asset_leaves_missing_files_unversioned(app, tmp_path):
    app.static_folder = str(tmp_path)

    assert await _render_asset(app, "vendor/missing.js") == "/assets/vendor/missing.js"
