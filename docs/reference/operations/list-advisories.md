# List Advisories

The `list-advisories` operation lists the repository security advisories in a given organization, with the ability to filter by the state of the advisories.

## Options

```shell
  --local                    work in local mode, not updating the referenced default config
  -c, --config FILE          configuration file to use  [default: otterdog.json]
  -v, --verbose              enable verbose output (-vvv for more verbose output)
  -s, --state [triage|draft|published|closed|all]
                             filter advisories by state(s) [default: triage,draft]
  -d, --details              display advisory details
  -h, --help                 Show this message and exit.
```

## Example

```shell
$ otterdog list-advisories eclipse-ee4j --state published --details

Listing published repository security advisories:

Organization ee4j[id=eclipse-ee4j] (1/1)
  Found 1 advisories with state 'published'.

  advisory['GHSA-c43q-5hpj-4crv'] {
    author                            = {
      avatar_url                        = "https://avatars.githubusercontent.com/u/15908245?v=4"
      events_url                        = "https://api.github.com/users/jansupol/events{/privacy}"
      followers_url                     = "https://api.github.com/users/jansupol/followers"
      following_url                     = "https://api.github.com/users/jansupol/following{/other_user}"
      gists_url                         = "https://api.github.com/users/jansupol/gists{/gist_id}"
      gravatar_id                       = ""
      html_url                          = "https://github.com/jansupol"
      id                                = 15908245
      login                             = "jansupol"
      node_id                           = "U_kgDOAPK9lQ"
      organizations_url                 = "https://api.github.com/users/jansupol/orgs"
      received_events_url               = "https://api.github.com/users/jansupol/received_events"
      repos_url                         = "https://api.github.com/users/jansupol/repos"
      site_admin                        = false
      starred_url                       = "https://api.github.com/users/jansupol/starred{/owner}{/repo}"
      subscriptions_url                 = "https://api.github.com/users/jansupol/subscriptions"
      type                              = "User"
      url                               = "https://api.github.com/users/jansupol"
      user_view_type                    = "public"
    }
    closed_at                         = null
    ...
```
