# CLI Operations

The CLI has support for various operations to operate on individual organizations. In general, if no organization is specified,
the selected operation runs on all organizations defined in the used configuration file (_otterdog.json_).

```shell
Usage: otterdog [OPTIONS] COMMAND [ARGS]...

  Managing GitHub organizations at scale.

Options:
  --version   Show the version and exit.
  -h, --help  Show this message and exit.

Commands:
  apply              Apply changes based on the current configuration to the live configuration at GitHub.
  canonical-diff     Displays a diff of the current configuration to a canonical version.
  delete-file        Deletes a specified file in a repository.
  dispatch-workflow  Dispatches a specified workflow in a repository.
  fetch-config       Fetches the configuration from the corresponding config repo of an organization.
  import             Imports existing resources for a GitHub organization.
  list-apps          Lists all installed GitHub apps for an organization.
  list-members       Displays the 2FA status of members of an organization.
  local-plan         Show changes to another local configuration.
  plan               Show changes to live configuration on GitHub.
  push-config        Pushes the local configuration to the corresponding config repo of an organization.
  show               Displays the full configuration for an organization.
  show-default       Displays the default configuration for an organization.
  show-live          Displays the live configuration for organizations.
  sync-template      Sync contents of repositories created from a template repository.
  validate           Validates the configuration for organizations.
  web-login          Open a browser window logged in to the GitHub organization.
```

## Working directory

When running `otterdog`, all used data is stored and accessed locally. The configuration files for each
organization are expected to be at location `$CWD/<config-dir>/<github-id>/`, where `<config-dir>` can be configured
in `otterdog.json` and defaults to `orgs`.

## GitHub API usage statistics

Every operation that processes organizations can report the requests it has sent to GitHub, to understand the cost
of an operation and to find room for optimization:

- `--stats` (or `OTTERDOG_STATS=1`) prints a summary to stderr once the operation has finished, failed or been
  interrupted, including the 10 organizations that sent the most requests. Any output of the operation on stdout,
  e.g. `list-apps --json`, stays untouched.
- `--stats-file <file>` (or `OTTERDOG_STATS_FILE=<file>`) writes the statistics as JSON to the given file,
  including the requests per organization and per endpoint.
- with `-v`, a one-line summary is logged for each organization, and `--stats` lists all organizations as well as
  the top endpoints.

```shell
$ otterdog plan --stats

...

GitHub API usage · plan · 3 organizations · 2m 41s
 API       Requests   Retries   Errors   Cached     Quota cost
────────────────────────────────────────────────────────────────
 REST         3,912         5       93    2,604   ~1,308 core
 GraphQL        148         0        0        0    171 points

 Total        4,060         5       93    2,604

  Errors:      404: 86 · 502: 5 · 403: 2
  Rate limit:  core     3,402/5,000 left  resets 14:32 UTC
               graphql  4,780/5,000 left  resets 14:40 UTC

Per organization
 Organization   Requests   Retries   Errors   Cached                Quota cost
───────────────────────────────────────────────────────────────────────────────
 eclipse-foo       2,201         3       52    1,420   ~701 core · 95 points
 eclipse-bar       1,318         2       30      834   ~436 core · 52 points
 eclipse-baz         541         0       11      350   ~171 core · 24 points
```

Every HTTP request that is actually sent counts as one request, including every page of a paginated result,
every retried attempt, every followed redirect and every request resent by the HTTP client on a new connection. Retries, errors and cached responses are subsets of the requests,
the quota cost is measured apart:

| Column     | Description                                                                                          |
|------------|------------------------------------------------------------------------------------------------------|
| Retries    | requests that repeat a failed attempt                                                                |
| Errors     | requests that failed with an HTTP status >= 400, or a network error or timeout once sent; for GraphQL also responses reporting errors in their body |
| Cached     | requests answered with `304 Not Modified` or served by a caching proxy                               |
| Quota cost | points deducted from the GitHub rate limits, see [Quota cost and rate limits](#quota-cost-and-rate-limits) |

A response that is served from the local cache without contacting GitHub is not a request. Neither is an attempt
that fails before being sent, e.g. as no connection to GitHub could be established, or as it timed out or was
interrupted while waiting for a free connection of the connection pool: such attempts are listed apart as `Not sent`. Many `404` errors are expected, as some settings are
only available depending on the plan of an organization.

Page loads of the GitHub web interface, used for settings that are not available via the api, are listed as
`Web UI` and do not count against any api quota. Cloning the default configuration with git is not accounted.

### Quota cost and rate limits

GitHub limits the use of its apis per hour, with a separate quota for each **resource**. Each response tells which
resource it has been accounted to, and the statistics use that name:

| Resource  | Covers                                                                            |
|-----------|-----------------------------------------------------------------------------------|
| `core`    | almost every REST endpoint                                                        |
| `graphql` | the GraphQL api, accounted in points                                              |
| others    | specific endpoints with their own, often smaller quota, e.g. `webhook_deliveries` |

A REST cost may thus be split across several resources, e.g. `~54 core, 4 webhook_deliveries`.

The quota cost of a run is the number of points it has deducted from these quotas:

- **REST** (`~1,308 core`): GitHub does not report the cost of a REST request, so it is estimated from its documented
  rules, hence the `~`. Every response costs one point, including errors and retries, except responses with
  `304 Not Modified`: otterdog revalidates its cached responses with conditional requests, which GitHub answers for
  free if nothing has changed. The estimate is thus close to the number of requests minus the cached ones.
- **GraphQL** (`171 points`): every query asks GitHub for its cost, so the value is exact. A query costs at least one
  point, more if it requests many nested items; as otterdog fetches results in pages of 100 items, most queries cost
  a single point. Mutations and failed requests do not report their cost and are listed as `+ N unpriced`.

The `Rate limit` lines show, for each resource used during the run, the points left (`3,402`), the size of the quota
for the used credentials (`5,000`) and when the quota is reset. The size depends on the
credentials, e.g. 5,000 requests per hour for a personal access token, see
[rate limits for the REST API](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api) and
[rate limits for the GraphQL API](https://docs.github.com/en/graphql/overview/rate-limits-and-query-limits-for-the-graphql-api).
The points left are the lowest value GitHub reported during the current window. They only decrease with requests that
are accounted: a run answered mostly with `304 Not Modified` hardly changes them. Responses served by a caching proxy
are ignored, as they carry the rate limit of the original request. As the quota is shared with any other client using
the same credentials, it can not be used to derive the consumption of a single run.

GitHub also enforces secondary rate limits, e.g. on concurrent requests, which are not measured.
