---
name: github-resource-type
description: Add support for a new GitHub resource type in otterdog, an organization-level or repository-level collection with its own identity, live inventory, configuration, import, plan and apply lifecycle. Covers the contract of the resource and its effect on existing configurations, the wiring into the parent model, the Jsonnet template, the schemas and the docs, the lifecycle (adoption, creation, update, rename, deletion), and the tests from diff to HTTP calls. Use it when asked to support a resource that otterdog does not manage yet. For a property of an existing resource, use github-config-property.
---

# Add a GitHub resource type

The conventions, commands, git rules and GitHub safety rules are in `AGENTS.md`, and the pipeline is described in
`docs/developing_otterdog/architecture.md`. The semantics of each field (absent values, status codes, defaults,
automatic retries) follow the `github-config-property` skill; this skill covers what a collection adds.

Organization variables are the simplest keyed collection to trace end to end, and the paths below use them as the
example. Trace a resource with the same parent and a similar lifecycle the same way, and check the wiring in the
checkout rather than trusting this list.

## 1. Define the contract of the resource

Write the contract down. Ask the user for a decision only when omission, adoption or deletion can change what
existing configurations plan, and the request does not settle it; a resource that follows an established contract
needs no stop.

- **Identity**: the parent (organization, repository, environment) and every supported scope; the key in the
  configuration (`metadata={"key": True}`, as `name` in `variable.py`), its uniqueness and normalization within the
  parent; the GitHub identifier used for writes; how a resource created by hand is matched, and what happens on a
  duplicate or ambiguous match. `associate_by_key` in `otterdog/utils.py` raises on a duplicate key while the patches
  are generated; reject duplicates in `validate()` first, with a message that names the resource.
- **Operations**: for list, read, create, update, rename and delete, the endpoint, permission, GitHub plan and
  response shape, from GitHub's documentation and sanitized fixtures. Record the unsupported operations and how
  otterdog reports them.
- **Rename**: an alias and a rename are two different things. An alias (a `model_only` field returned by
  `get_all_key_values`, as in `webhook.py` and for repositories) lets the new key find the existing object. Whether
  that object can then be renamed depends on the API: check it. If the API renames in place, the rename is an
  update that keeps the GitHub identifier. If it only allows a replacement, a deletion and a creation, define what
  `apply` does without `--delete-resources`, so that it does not leave a second object next to the old one by
  accident.
- **Omission**: choose explicitly whether omitting the collection means *unmanaged* (not read, no patch) or
  *managed and empty* (every live item is a removal). The existing collections are managed and empty: the parent
  constructor of the template sets them to `[]` (`variables: []` in `otterdog-defaults.libsonnet`), and the mapping
  of the parent turns an absent key into `[]` as well (`OptionalS("variables", default=[])` in
  `github_organization.py`), so omission and `[]` cannot be told apart. *Unmanaged* exists today only at the level
  of the template: without the constructor, `default_org_variable_config` in `jsonnet.py` is `None`, and
  `_load_variables` does not read the live collection. Choosing *unmanaged* on omission with a template that defines
  the type therefore needs a change to the template and to the parent mapping. With *managed and empty*, once an
  organization uses a template that defines the type, every live item it already has is planned as a removal, which
  `apply --delete-resources` deletes.
- **Values**: which values can be imported and compared. Keep provider ids out of the configuration when they only
  address API calls (`external_only`). For write-only values, see `secret.py`: the provider returns a dummy
  `********` value, which is never compared, and an item whose configured value is a dummy is skipped
  (`include_for_live_patch`).

## 2. Wire the model, the inventory and the configuration

| Piece             | Example: organization variables                                                           |
|-------------------|-------------------------------------------------------------------------------------------|
| Model             | `otterdog/models/organization_variable.py`, based on `variable.py`                        |
| Parent collection | `variables` in `GitHubOrganization` (`github_organization.py`): the field, `add_variable` / `set_variables`, the mapping from the configuration, validation, and the `variables+:` block of `to_jsonnet` used by `import` |
| Live inventory    | `_load_variables` in `GitHubOrganization.load_from_provider`, `get_org_variables` in `otterdog/providers/github/__init__.py`, `get_variables` in `rest/org_client.py` |
| Patches           | `OrganizationVariable.generate_live_patch_of_list(...)` in `GitHubOrganization.generate_live_patch` |
| Jsonnet           | `newOrgVariable` and its export, and `variables: []` in `newOrg`, in `otterdog-defaults.libsonnet`; `create_org_variable` and `default_org_variable_config` in `otterdog/jsonnet.py` |
| Schema            | `otterdog/resources/schemas/org-variable.json`, referenced from `organization.json`       |
| `show-default`    | `otterdog/operations/show_default.py`                                                     |
| Docs              | `docs/reference/organization/variable.md`, its nav entry in `zensical.toml`, then `make playground-examples` |
| Tests             | `tests/models/test_org_variable.py`, `tests/providers/github/integration/test_org_variables.py` |

- Load the full live collection under the right parent, with pagination and detail requests where needed. A
  confirmed empty collection is valid. A failed or incomplete inventory must raise before any patch is computed or
  any import is written from it; see `tests/providers/github/integration/test_secret_read_failures.py`. Optional
  fields that are unavailable follow their own contract (`github-config-property`).
- Trace the collection through the `import`, `plan` and `apply` entry points. When shared code changes, check the
  local operations and the webapp tasks that run them. `import` must write a valid configuration for the fields
  GitHub exposes, and keep secrets and credentials out of its output and of the logs.

## 3. Implement the lifecycle

- **Create** only when a complete inventory shows that the item is absent. **Adopt** an existing item by its key
  within the right parent. **Update** it through its GitHub identity, and keep unrelated values when the endpoint
  needs a full payload.
- **Delete** only through the opt-in of `--delete-resources` (`operations/apply.py`), and check that the target
  belongs to the right parent.
- **Order**: `apply` runs the patches in the order `generate_live_patch` of the parent produces them, except those
  that make an object read-only, which run last. If the resource depends on another item created or removed by the
  same `apply`, place its `generate_live_patch_of_list` call accordingly.
- **Errors and retries**: interpret each response, and check what a lost response does to a creation, and what an
  automatic retry does to a write sent with `PUT` or `DELETE`, as the Provider section of `github-config-property`
  describes; test both the outcome within one `apply` and the reconciliation by a later run (its Tests section).
  For a collection, a 409 or 422 after a creation needs evidence before it is read as "already exists".

## 4. Test through diff and apply

Use sanitized fixtures and mocked GitHub calls, never GitHub. Check the exact method, path, resource id and payload
of the expected calls: the HTTP mock of the integration tests fails on any unexpected request. The import round trip
can use `evaluate_generated_jsonnet` in `tests/models/__init__.py`, which writes the Jsonnet of an object the way
`import` does and evaluates it against the template.

| Starting state | Expected result |
| --- | --- |
| Collection omitted, items present on GitHub | With the old template (no constructor) and the new one, after real Jsonnet loading: `plan` follows the chosen meaning of omission, `apply` without `--delete-resources` deletes nothing, and `apply --delete-resources` does what that meaning implies. |
| Collection declared as `[]`, items present on GitHub | Tested separately from omission, with the same templates and `apply` modes: the plan and the deletions match a managed, empty collection. |
| Item created by hand on GitHub | Import, then load and plan: no mutation for the observable fields. An equivalent declaration matches the item and creates nothing. One field changed gives the expected update calls, then a fresh plan is empty. |
| Desired item absent from a complete inventory | Created under the right parent; a plan against the resulting inventory is empty. |
| Several parents hold the same key | Only the intended parent is patched. A duplicate within a parent is rejected by `validate()`. |
| Desired item removed | `apply` without `--delete-resources` deletes nothing; `apply --delete-resources` deletes only that item, in the right parent. |
| Item renamed, the API renames in place | Matched through its alias; one update keeps the GitHub identifier; no creation or deletion is sent. |
| Item renamed, the API only replaces | `apply` without `--delete-resources` does not leave a second object next to the old one by accident; the documented replacement happens with the opt-in. |
| Inventory, or one of its pages, fails | The failure is reported; no mutation for that scope, and no import that presents a partial state as complete. |
| Apply succeeds in part, or an applied write loses its response | A fresh apply reads the current state and sends only the remaining mutations. The outcome within the same apply, which depends on the method of the write, is tested with the real requester against the local server, as `github-config-property` describes. |

## 5. Checks and report

Run the model, provider, integration and schema tests of the resource, plus the Jsonnet, docs and Playground checks
that `AGENTS.md` lists for the files touched, and `make test`, since `github_organization.py` and `jsonnet.py` are
shared code. Use a real GitHub organization only when the user explicitly asks for it.

Report the supported scopes and operations, the chosen meaning of omission, how a rename is handled, the effect on
existing configurations (`apply` with and without `--delete-resources`, old and new template), and the checks that
ran and were skipped.
