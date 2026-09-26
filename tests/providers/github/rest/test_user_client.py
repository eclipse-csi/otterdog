import pytest
from pretend import stub

from otterdog.providers.github.exception import GitHubException
from otterdog.providers.github.rest.user_client import UserClient


@pytest.mark.parametrize(
    "method_name,argument,expected_url,expected_result",
    [
        ("get_user_ids", "alice", "/users/alice", (123, "user-node-id")),
        ("get_user_login", 123, "/user/123", "alice"),
    ],
)
async def test_user_resolution(method_name, argument, expected_url, expected_result):
    async def request_json(method, url):
        assert method == "GET"
        assert url == expected_url
        if method_name == "get_user_ids":
            return {"id": 123, "node_id": "user-node-id"}
        return {"login": "alice"}

    client = UserClient(stub(requester=stub(request_json=request_json)))

    assert await getattr(client, method_name)(argument) == expected_result


@pytest.mark.parametrize(
    "method_name,argument",
    [("get_user_ids", "alice"), ("get_user_login", 123)],
)
async def test_user_resolution_translates_github_error(method_name, argument):
    async def request_json(method, url):
        raise GitHubException(url, 404, "not found")

    client = UserClient(stub(requester=stub(request_json=request_json)))

    with pytest.raises(RuntimeError, match="failed retrieving user"):
        await getattr(client, method_name)(argument)
