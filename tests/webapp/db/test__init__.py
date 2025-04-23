#  *******************************************************************************
#  Copyright (c) 2025 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************
import pytest
from webapp.db import _parse


@pytest.mark.parametrize(
    "mongodb_url, expected_result, expected_error",
    [
        ("mongodb://root:secret@mongodb:27017/otterdog", ("mongodb://root:secret@mongodb:27017", "otterdog"), None),
        ("mongodb://mongodb:27017/otterdog", ("mongodb://mongodb:27017", "otterdog"), None),
        (
            "mongodb://root:secret@otterdog-mongodb.default.svc.cluster.local:27017/otterdog",
            ("mongodb://root:secret@otterdog-mongodb.default.svc.cluster.local:27017", "otterdog"),
            None,
        ),
        (
            "mongodb://otterdog-mongodb.default.svc.cluster.local:27017/otterdog",
            ("mongodb://otterdog-mongodb.default.svc.cluster.local:27017", "otterdog"),
            None,
        ),
        ("mongodb://mongodb.example.com:27017/otterdog", ("mongodb://mongodb.example.com:27017", "otterdog"), None),
        (
            "mongodb://:secret@mongodb.example.com:27017/otterdog",
            ("mongodb://:secret@mongodb.example.com:27017", "otterdog"),
            None,
        ),
        ("mongodb://mongodb:27017", None, "invalid mongo connection uri, no database"),
        ("mongodb:27017", None, "invalid mongo connection uri, no scheme"),
    ],
)
def test__parse(mongodb_url, expected_result, expected_error):
    if expected_error:
        with pytest.raises(RuntimeError) as err:
            _parse(mongodb_url)
            assert expected_error in str(err)

    else:
        result = _parse(mongodb_url)
        assert result == expected_result
