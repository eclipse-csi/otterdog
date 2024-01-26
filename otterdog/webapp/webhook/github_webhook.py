#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

# Original code from https://github.com/go-build-it/quart-github-webhook
# licensed under Apache License Version 2.0

import collections
import hashlib
import hmac
import json
import logging

from quart import abort, request


class GitHubWebhook(object):
    def __init__(self):
        self._endpoint = None
        self._secret = None
        self._hooks = collections.defaultdict(list)
        self._logger = logging.getLogger(__name__)

    def init_app(self, app) -> None:
        """
        Initializes this webhook on the given :code:`app`.
        """

        self._endpoint = app.config["GITHUB_WEBHOOK_ENDPOINT"]

        secret = app.config["GITHUB_WEBHOOK_SECRET"]
        if secret is not None and not isinstance(secret, bytes):
            secret = secret.encode("utf-8")
        self._secret = secret

        app.add_url_rule(
            rule=self._endpoint,
            endpoint=self._endpoint,
            view_func=self._post_receive,
            methods=["POST"],
        )

    def hook(self, event_type):
        """
        Registers a function as a hook. Multiple hooks can be registered for a given type, but the
        order in which they are invoke is unspecified.

        :param event_type: The event type this hook will be invoked for.
        """

        def decorator(func):
            self._hooks[event_type].append(func)
            return func

        return decorator

    async def _get_digest(self):
        """Return message digest if a secret key was provided"""

        if self._secret:
            return hmac.new(self._secret, await request.data, hashlib.sha1).hexdigest()

    async def _post_receive(self):
        """Callback from Flask"""

        digest = await self._get_digest()

        if digest is not None:
            sig_parts = _get_header("X-Hub-Signature").split("=", 1)
            if not isinstance(digest, str):
                digest = str(digest)

            if len(sig_parts) < 2 or sig_parts[0] != "sha1" or not hmac.compare_digest(sig_parts[1], digest):
                abort(400, "Invalid signature")

        event_type = _get_header("X-Github-Event")
        content_type = _get_header("content-type")
        if content_type == "application/x-www-form-urlencoded":
            formdata = (await request.form).to_dict(flat=True)
            data = json.loads(formdata["payload"])
        elif content_type == "application/json":
            data = await request.get_json()
        else:
            abort(415, f"Unknown content type {content_type}")

        if data is None:
            abort(400, "Request body must contain data")

        self._logger.info(
            "%s (%s)",
            _format_event(event_type, data),
            _get_header("X-Github-Delivery"),
        )

        for hook in self._hooks.get(event_type, []):
            await hook(data)

        return "", 204


def _get_header(key):
    """Return message header"""

    try:
        return request.headers[key]
    except KeyError:
        abort(400, "Missing header: " + key)


EVENT_DESCRIPTIONS = {
    "commit_comment": "{comment[user][login]} commented on " "{comment[commit_id]} in {repository[full_name]}",
    "create": "{sender[login]} created {ref_type} ({ref}) in " "{repository[full_name]}",
    "delete": "{sender[login]} deleted {ref_type} ({ref}) in " "{repository[full_name]}",
    "deployment": "{sender[login]} deployed {deployment[ref]} to "
    "{deployment[environment]} in {repository[full_name]}",
    "deployment_status": "deployment of {deployement[ref]} to "
    "{deployment[environment]} "
    "{deployment_status[state]} in "
    "{repository[full_name]}",
    "fork": "{forkee[owner][login]} forked {forkee[name]}",
    "gollum": "{sender[login]} edited wiki pages in {repository[full_name]}",
    "issue_comment": "{sender[login]} commented on issue #{issue[number]} " "in {repository[full_name]}",
    "issues": "{sender[login]} {action} issue #{issue[number]} in " "{repository[full_name]}",
    "member": "{sender[login]} {action} member {member[login]} in " "{repository[full_name]}",
    "membership": "{sender[login]} {action} member {member[login]} to team "
    "{team[name]} in "
    "{repository[full_name]}",
    "page_build": "{sender[login]} built pages in {repository[full_name]}",
    "ping": "ping from {sender[login]}",
    "public": "{sender[login]} publicized {repository[full_name]}",
    "pull_request": "{sender[login]} {action} pull #{pull_request[number]} in " "{repository[full_name]}",
    "pull_request_review": "{sender[login]} {action} {review[state]} "
    "review on pull #{pull_request[number]} in "
    "{repository[full_name]}",
    "pull_request_review_comment": "{comment[user][login]} {action} comment "
    "on pull #{pull_request[number]} in "
    "{repository[full_name]}",
    "push": "{pusher[name]} pushed {ref} in {repository[full_name]}",
    "release": "{release[author][login]} {action} {release[tag_name]} in " "{repository[full_name]}",
    "repository": "{sender[login]} {action} repository " "{repository[full_name]}",
    "status": "{sender[login]} set {sha} status to {state} in " "{repository[full_name]}",
    "team_add": "{sender[login]} added repository {repository[full_name]} to " "team {team[name]}",
    "watch": "{sender[login]} {action} watch in repository " "{repository[full_name]}",
}


def _format_event(event_type, data):
    try:
        return EVENT_DESCRIPTIONS[event_type].format(**data)
    except KeyError:
        return event_type
