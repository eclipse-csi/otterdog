---
name: github-config-property
description: Add or change a setting of a GitHub resource managed by otterdog, such as organization settings, a repository, team, ruleset, environment, webhook, secret or variable. Covers the model field, the default template, reading the live state, diff, apply, the JSON schema, tests and reference docs. Use it when asked to support a new GitHub setting, change the default of an existing one, or fix how one is read, compared or applied (for example a diff that `plan` always reports).
---

# Add or change a GitHub configuration property

The conventions, commands and GitHub safety rules are in `AGENTS.md`. The pipeline this skill touches is described
in `docs/developing_otterdog/architecture.md`.

## When to use

- A GitHub setting is not supported yet. `docs/userguide/unsupported.md` may list it.
- An existing property has a wrong default, is read or written incorrectly, or `plan` keeps reporting a change for
  it after `apply`.

A whole new resource type is out of scope: use the `github-resource-type` skill, then the steps below for each field
of the resource.

## 1. Define the contract of the field

Write the contract down before touching the model or the provider. Use GitHub's documentation and sanitized response
fixtures when available (`tests/models/resources/github-*.json`), not a neighbouring field, which can look
the same and behave differently. Calls to a real organization are reserved for an explicit request (see "Checks").

- **Read**: the endpoint or query that returns the value (REST, GraphQL, or web UI only), the plan and the permission
  it needs, and the format of the value.
- **Write**: the endpoint that changes the value, its permission and the format it expects. It can differ from the
  read side: a value returned in the main payload of the resource can need a dedicated call to be written.
- **Status codes**: what each one means for this endpoint. For example, `_fill_immutable_releases` in
  `rest/repo_client.py` reads a 404 as "disabled" (`False`), while on another endpoint a 404 can mean an unavailable
  feature or a missing resource. Its handling of 402 and 403 is not a model to copy: it reads a denied access, a
  missing scope included, as an unavailable feature. For an optional read, use `_get_optional_json` with the
  arguments that "Provider" gives.
- **Absent and empty values**: what happens when the configuration omits the field, when GitHub omits it, and when
  either side gives an explicit `null`, `false` or `[]`. In the diff, a value that is `UNSET` on either side is not
  compared, while `None`, `False` and `[]` are (`get_difference_from` in `otterdog/models/__init__.py`). An omitted
  field gets its dataclass default, if it has one, instead of `UNSET` (`_DefaultValuesMixin`).
- **Existing configurations**: what an existing configuration, which does not mention the field, will plan after the
  change.

Then locate the files of the resource:

| Resource           | Model (`otterdog/models/`)                                                  | Provider (`otterdog/providers/github/`) | Schema (`otterdog/resources/schemas/`)                    | Reference doc (`docs/reference/organization/`) | Tests (`tests/models/`) |
|--------------------|-----------------------------------------------------------------------------|-----------------------------------------|-----------------------------------------------------------|------------------------------------------------|-------------------------|
| Org settings       | `organization_settings.py`                                                  | `rest/org_client.py`, `web.py`          | `settings.json`                                           | `settings.md`                                  | `test_org_settings.py`  |
| Workflow settings  | `workflow_settings.py`, `organization_workflow_settings.py`, `repo_workflow_settings.py` | `rest/org_client.py`, `rest/repo_client.py` | `workflow-settings.json`, `org-workflow-settings.json`, `repo-workflow-settings.json` | `settings.md`, `repository/index.md` | `test_workflow_settings.py` |
| Repository         | `repository.py`                                                             | `rest/repo_client.py`, `graphql.py`     | `repository.json`                                         | `repository/index.md`                          | `test_repository.py`    |
| Others             | `<resource>.py` (e.g. `ruleset.py`, `team.py`, `environment.py`, `webhook.py`) | the matching `rest/*_client.py`      | the file with the same name                               | the page of the resource                       | `test_<resource>.py`, or one file per scope (e.g. `test_org_webhook.py`, `test_repo_webhook.py`) |

The default value of a resource comes from its `orgs.new*` function in
`otterdog/resources/defaults/otterdog-defaults.libsonnet`. The function names are mapped in `otterdog/jsonnet.py`.

## 2. Model

In `otterdog/models/<resource>.py`:

1. Add the dataclass field next to the related fields. Use metadata flags where they apply: `read_only` for values
   that are compared and shown by `plan` with a note, but never sent; `model_only` for values that exist only in the
   configuration and are neither compared nor sent; `external_only` for values that exist only on GitHub, such as
   ids, and are not part of the configuration.
2. `validate()`: check the allowed values, the plan, and the dependencies on other fields with
   `context.add_failure(...)`, and match the wording of the existing messages. A set of allowed values that the
   schema repeats as an `enum` is checked against it in `tests/schemas/test_allowed_values.py`.
3. Live state, in `get_mapping_from_provider`: a key with the same name and shape as the API needs no code. Map the
   key explicitly when the API name or structure differs. Choose the value of a missing key from the contract of
   step 1, and tell two cases apart:
    - **An optional field whose unavailability is established** (the plan, a permission, a status that step 1
      documents): `UNSET` (`OptionalS(..., default=UNSET)`), so that it is not compared. Use `None`, `False` or `[]`
      only when GitHub confirms that value.
    - **An incomplete inventory**, a read that leaves unknown which resources exist (a failed list request or page):
      raise, so that no patch is computed for that scope. Otherwise a resource missing from the read becomes a
      creation, and `import` drops it from the configuration; see
      `tests/providers/github/integration/test_secret_read_failures.py`.
4. Writing, in `get_mapping_to_provider`: rename or convert values (e.g. repository names to ids with
   `provider.get_repo_ids`), and drop the keys the endpoint does not accept.
5. Diff: every field that is not `model_only` is compared. For a field that only matters in some cases, override
   `include_field_for_diff_computation`; `immutable_releases_selected_repositories` in
   `organization_settings.py` is an example. Repository values that an organization policy overrides are
   reconciled in `Repository.coerce_from_org_settings`.
6. Apply: `apply_live_patch` usually needs no change for a new field of an existing resource. Settings that are only
   available in the web UI (`"provider": "web"` in `settings.json`) are skipped with `--no-web-ui`. Changes that can
   cost money are flagged by `is_cost_related` (`CostPolicy`).

`to_jsonnet` writes only the values that differ from the template default, so the default also shapes the output of
`import`.

## 3. Provider

- A field that the main payload of the resource both returns and accepts needs nothing here. Check the two sides
  separately (step 1): being returned by the main read does not mean the main update accepts it.
- Otherwise, read and write it in the client that assembles the resource: see the `_fill_*` / `_update_*` pairs in
  `rest/repo_client.py`, and `get_settings` / `update_settings` in `rest/org_client.py`. Remove the key from the
  update payload and send it to its own endpoint.
- Interpret each response for this endpoint and this operation, from the contract of step 1, not by copying a
  neighbouring helper:
    - **401, 403, 404**: tell bad credentials, missing permissions (`InsufficientPermissionsException`,
      `_is_access_denied` in `rest/__init__.py`), an unavailable feature and a missing resource apart. `request_json`
      raises `BadCredentialsException` on a 401; `request_raw` returns the status and leaves it to the caller, except
      for a 403 caused by missing OAuth scopes, on which the requester raises `InsufficientPermissionsException`.
      Neither exception is a `RuntimeError`: catch them explicitly, and report a missing permission as such. Do not
      copy `_fill_immutable_releases` here: it catches `InsufficientPermissionsException` but then leaves the value
      `UNSET` as if the feature were unavailable. For an
      optional read, `_get_optional_json` in `rest/__init__.py` helps, but not with its defaults, which read every 402,
      403 and 404 as "unavailable": pass `raise_on_access_denied=True`, as `team_client.py` does, and limit
      `unavailable_statuses` to the statuses that step 1 found to mean "unavailable" on this endpoint. A read whose
      meaning is uncertain must never lead to a creation or a deletion based on a supposed absence. Log a warning when
      a value is left `UNSET`.
    - **Rate limit (403 or 429)**: it is neither an unavailable feature nor a denied access, and must raise;
      `_get_optional_json` and `_fill_immutable_releases` do so, with the predicate `is_rate_limited` of
      `rest/requester.py`. Check it also on the message of an `InsufficientPermissionsException`: the requester raises
      it for a 403 whenever a scope of `X-Accepted-OAuth-Scopes` is not granted, whatever the cause of the 403, a rate
      limit included. The REST requester already sends a rate-limited request again, up to 3 times, after the wait
      GitHub asks for (`get_rate_limit_wait`), and returns the last response once the retries are exhausted or the wait
      exceeds 5 minutes, so a rate limit that reaches the provider is final. Do not add a retry loop in a helper: a
      waiting policy belongs in `rest/requester.py`, and needs the user's agreement.
    - **409**: find out what the conflict means for this endpoint. When a creation conflicts because the resource
      already exists (created in between, or by a retried request), read it again and check its identity before
      adopting it. When an update conflicts, report it, or recompute the diff from the current state if the provider
      can.
    - **422 and other unexpected 4xx**: raise with the operation, the resource, the status, and the message and
      structured `errors` of the response, without tokens or secret values. Treat a response as "setting
      unavailable" only when evidence confirms that meaning for this endpoint, and then match that exact response,
      not the status alone. Test it in `tests/providers/github/rest/test_<client>.py` together with another response
      of the same status that must still fail, so that a targeted exception does not become a skip of every 422 that
      also hides payload errors.
    - **5xx or lost response during a write**: the outcome is unknown, because GitHub may have applied the write. The
      REST requester (`get_retry_options` in `rest/requester.py`) makes up to 3 attempts on any 5xx and any exception
      raised before the response is returned, only for the idempotent methods `GET`, `HEAD`, `OPTIONS`, `PUT` and
      `DELETE`. Within an attempt, aiohttp itself resends such a request once when its connection is closed or reset
      before a response arrives, and a body cut off after the headers is retried only when the cached session reads it
      to cache it (`tests/providers/github/test_request_recording.py`). A `POST` or `PATCH` is sent again only when no
      connection could be established: otherwise the provider gets the 5xx or the exception, and must report the
      failure, since the next run reads the actual state. Before wiring a mutation sent with `PUT` or `DELETE`, check
      that a repeated call has the same effect on this endpoint; if it can apply the change twice, tell the user before
      wiring it: the retry policy is shared code. A 404 after a retried `DELETE`, or a 409 or 422 after a retried `PUT`,
      can mean that the first attempt succeeded. The GraphQL client (`graphql.py`) still retries every query and
      mutation on any 5xx and exception.
- Any other response is an explicit failure: raise a `RuntimeError` with the operation, the organization, the
  repository and the status. On a read, turning it into `UNSET` hides a provider error and leaves the plan
  incomplete. On a write, treating it as a success leaves GitHub unchanged, and the same diff comes back at the next
  `plan`.
- GraphQL queries are stored in `otterdog/resources/graphql/`.

## 4. Schema and default template

- Add the key to `otterdog/resources/schemas/<resource>.json`. Unknown keys are rejected: by
  `additionalProperties: false`, or, in a scoped schema that extends a base schema with `$ref` (variables, secrets,
  rulesets, roles, workflow settings, environments), by `unevaluatedProperties: false`. Do not add
  `additionalProperties: false` to a base schema such as `variable.json`: it would reject the keys of one scope. In
  `settings.json`, set `"provider": "restapi"` or `"web"`, which decides how the key is read.
- Choose the default in the matching `new*` function of `otterdog-defaults.libsonnet` from its effect on existing
  configurations: they omit the field, so the template default applies to all of them at the next `plan`. GitHub's
  default at creation can depend on the plan or on an organization policy, so it does not guarantee an empty plan.
  If omitting the field must keep the value set on GitHub, verify that the field resolves to `UNSET` after Jsonnet
  evaluation and model loading (see the test "Field omitted, through the real template"). Add a comment if the value
  depends on another one.
- Changing an existing default changes the next `plan`/`apply` of every organization that uses the template. The
  pull request template counts it as a breaking change, and its migration path goes in the description of the pull
  request (see the `pr-description` skill).

## 5. Tests

- Add the field to the fixtures in `tests/models/resources/`: `otterdog-<resource>.json` holds the configuration
  side and `github-<resource>.json` the API side (the names vary, e.g. `github-repo.json`, `github-org-settings.json`).
  Then assert it in `tests/models/test_<resource>.py`:
  `test_load_from_model`, `test_load_from_provider`, and `test_to_provider` (update the asserted number of keys),
  plus the patch and difference tests when the diff logic changed.
- **Start from a GitHub state that already holds the resource.** A test that starts from an empty organization covers
  neither the adoption of a resource created by hand nor the risk of overwriting its other settings. Build the live
  state with `from_provider_data` from a GitHub response, and the configuration with `from_model_data`. The resources
  of a list are matched by their `key` field (`get_all_key_values`, `generate_live_patch_of_list`); for a resource
  without a key, such as the organization settings, the same checks apply without the matching. In the integration
  tests (`github.http.expect(..., request_json=...)`, with the `generate_patch_and_run_it` helper of the file), the
  HTTP mock fails on any request that was not expected, and `verify_all_called` on any expected request that was not
  made. Cover the cases that apply:
    - **Existing resource, absent from the configuration**: the only patch is a removal, and `apply` sends no deletion
      without `--delete-resources` (`operations/apply.py`). Test that mode separately when it applies to the
      resource. Some types ignore existing objects (`include_existing_object_for_live_patch`).
    - **Existing resource, declared with the same values**: it is matched by its key, there is no patch, and `apply`
      sends no creation.
    - **Same resource, one field changed**: one logical update of the right resource, with the HTTP calls this
      endpoint needs (some fields need several), and the exact body of each. When the API needs the full object,
      check that the neighbouring values are kept.
    - **Field omitted, then explicitly `false`, `[]` or `null`**, with the values that make sense for the API: the
      omission follows the contract of step 1, and an explicit value gives the expected payload.
    - **Field omitted, through the real template**: evaluate a configuration that omits the field with
      `jsonnet_evaluate_snippet` on `otterdog-defaults.libsonnet`, as `ModelTest.test_example_config` does, load it
      with `from_model_data`, and compare it with a live state whose value differs from the default you consider. If
      omission must keep the value set on GitHub, the field resolves to `UNSET` and the diff holds no change for it.
      This catches a default that the template or the model injects before the comparison.
    - **Partial write**: the mocks keep no state, so build the live state the first run left (some resources
      updated, others not), then check that the second run sends only the remaining operations, and that the state
      after it gives no change.
    - **Write applied, response lost, within the same run**: the automatic retries happen inside the first `apply`,
      before the provider sees a response, and depend on the method (see the Provider section). The integration kit
      replaces `RetryClient` with the HTTP mock (`tests/providers/github/integration/conftest.py`), so it never
      exercises them. Use the real `Requester` against the local server of
      `tests/providers/github/rest/test_requester.py`: add a route to `_GitHubStub` that stores the write, then loses
      its response with a 502 or a dropped connection, as its `create_hook` and `disconnect` routes do. Check that
      the server holds exactly one resource at the end, whatever the number of attempts (`hits`), and that the result
      otterdog reports matches it. Lock this down before wiring a mutation sent with `PUT` or `DELETE`.
    - **Write applied, response lost, then a new run**: the next run reads the resource, adopts it, and creates no
      second one.
- **Priority regression test**: a resource created by hand, declared as is, then changed on one field. Check that
  there is no creation call, one logical update of the right resource with the expected calls and payload, and no
  change between the configuration and the live state after the update. This one path covers adoption, identity,
  patch and idempotence.
- `ModelTest.test_example_config` evaluates the default template, so it covers the new default.
- Test provider helpers in `tests/providers/github/rest/test_<client>.py` with `pretend` stubs. Test the behaviour
  from diff to HTTP calls in `tests/providers/github/integration/`.
- Add validation tests for each new error or warning, as in `test_validate_immutable_releases`.

## 6. Documentation

- Add a row to the property table of the reference page, and a rule to its "Validation rules" section if
  `validate()` changed.
- Remove the setting from `docs/userguide/unsupported.md` if it is listed there. Update the guide in
  `docs/userguide/guides/` that covers the topic; its Jsonnet examples must remain complete organizations.
- Run `make playground-examples` after changing a reference table or a guide example.

## 7. Checks

Choose the checks with the rules in `AGENTS.md`. For a typical property they are:

```shell
poetry run prek run --files <changed files>
poetry run pytest tests/models tests/providers/github tests/schemas tests/test_packaged_defaults.py
poetry run pytest tests/test_docs_examples.py        # template or docs changed
poetry run pytest tests/test_docs_playground.py      # reference tables or guide examples changed (playground catalogs)
make docs                                                                            # docs changed
```

Run `make test` if shared model or provider code changed. Check against a real organization (`otterdog plan` on a
test organization) only when the user asks for it.
