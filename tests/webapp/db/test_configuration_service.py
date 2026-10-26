#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from unittest import mock

from otterdog.webapp.db import service

_DOCUMENTS = [
    {"_id": "alpha-org", "config": {"github_id": "alpha-org"}, "jsonnet": "orgs.newOrg('alpha', 'alpha-org')"},
    # fetched before the source of the configurations was stored
    {"_id": "beta-org", "config": {"github_id": "beta-org"}},
    {"_id": "other-org", "config": {"github_id": "other-org"}, "jsonnet": "orgs.newOrg('other', 'other-org')"},
]


class _FakeCollection:
    def __init__(self):
        self.projections = []

    def find(self, query, projection):
        self.projections.append(projection)
        documents = [
            {"_id": document["_id"], **{key: document[key] for key in projection if key in document}}
            for document in _DOCUMENTS
            if document["_id"] in query["_id"]["$in"]
        ]
        return _FakeCursor(documents)


class _FakeCursor:
    def __init__(self, documents):
        self.documents = documents

    async def __aiter__(self):
        for document in self.documents:
            yield document


async def test_the_sources_of_the_configurations_are_loaded_without_their_evaluation(monkeypatch):
    collection = _FakeCollection()
    engine = mock.Mock()
    engine.get_collection.return_value = collection
    monkeypatch.setattr(type(service.mongo), "odm", mock.PropertyMock(return_value=engine))

    sources = await service.get_configuration_sources(["alpha-org", "beta-org", "new-org"])

    assert sources == {"alpha-org": "orgs.newOrg('alpha', 'alpha-org')", "beta-org": None}
    assert collection.projections == [{"jsonnet": True}]
