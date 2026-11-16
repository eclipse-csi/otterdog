#  *******************************************************************************
#  Copyright (c) 2025 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************
from unittest.mock import MagicMock

import pytest
import webapp.db as db_module
from quart import Quart
from webapp.db import Mongo, _database_from_uri


@pytest.mark.parametrize(
    "mongodb_url, expected_result, expected_error",
    [
        ("mongodb://root:secret@mongodb:27017/otterdog", "otterdog", None),
        ("mongodb://mongodb:27017/otterdog", "otterdog", None),
        (
            "mongodb://root:secret@otterdog-mongodb.default.svc.cluster.local:27017/otterdog",
            "otterdog",
            None,
        ),
        (
            "mongodb://otterdog-mongodb.default.svc.cluster.local:27017/otterdog",
            "otterdog",
            None,
        ),
        ("mongodb://mongodb.example.com:27017/otterdog", "otterdog", None),
        (
            "mongodb://:secret@mongodb.example.com:27017/otterdog",
            "otterdog",
            None,
        ),
        ("mongodb://mongodb:27017", None, "invalid mongo connection uri, no database"),
        ("mongodb:27017", None, "invalid mongo connection uri, no scheme"),
    ],
)
def test__database_from_uri(mongodb_url, expected_result, expected_error):
    if expected_error:
        with pytest.raises(RuntimeError) as err:
            _database_from_uri(mongodb_url)
            assert expected_error in str(err)

    else:
        result = _database_from_uri(mongodb_url)
        assert result == expected_result


def test_init_app_passes_full_uri(monkeypatch):
    mongo_uri = "mongodb://mongodb:27017/otterdog"

    captured_uris = []
    mock_client = MagicMock()

    def mock_motor_client(uri, *args, **kwargs):
        captured_uris.append(uri)
        return mock_client

    monkeypatch.setattr(db_module, "AsyncIOMotorClient", mock_motor_client)
    monkeypatch.setattr(db_module, "AIOEngine", MagicMock())

    app = Quart(__name__)
    app.config["MONGO_URI"] = mongo_uri

    mongo = Mongo()
    mongo.init_app(app)

    assert len(captured_uris) == 1
    assert captured_uris[0] == mongo_uri


async def test_ping_fails_when_the_server_is_unreachable():
    import socket

    from pymongo.errors import ServerSelectionTimeoutError

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]

    app = Quart(__name__)
    app.config["MONGO_URI"] = f"mongodb://127.0.0.1:{port}/otterdog?serverSelectionTimeoutMS=100"

    mongo = Mongo()
    mongo.init_app(app)

    with pytest.raises(ServerSelectionTimeoutError):
        await mongo.ping()


async def test_ping_gives_up_after_its_timeout():
    """
    Motor runs the command in a thread of a pool shared by the whole webapp.

    Cancelling the coroutine awaiting it would leave the thread blocked until the server
    selection timeout, 30s by default, the timeout has to bound the command itself.
    """
    import socket
    import time

    from pymongo.errors import PyMongoError

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]

    app = Quart(__name__)
    app.config["MONGO_URI"] = f"mongodb://127.0.0.1:{port}/otterdog"

    mongo = Mongo()
    mongo.init_app(app)

    started_at = time.monotonic()
    with pytest.raises(PyMongoError):
        await mongo.ping(timeout=0.2)

    assert time.monotonic() - started_at < 5
