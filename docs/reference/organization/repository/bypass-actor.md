A Bypass Actor represents an entity that is allowed to bypass the restrictions setup by a specific ruleset.
The following format is used to distinguish between the different types of actors that GitHub supports:

| Actor Type | Format                        | Example                    |
|------------|-------------------------------|----------------------------|
| Role       | `#<role-name>`                | `#Maintain`                |
| User       | `@<github_handle>`            | `@alice`                   |
| Team       | `@<organization>/<team-slug>` | `@OtterdogTest/committers` |
| App        | `<app-slug>`                  | `eclipse-eca-validation`   |

The following roles are currently supported:

- Write
- Maintain
- RepositoryAdmin
- OrganizationAdmin

!!! note

    Deploy keys cannot be specified as bypass actors. Secret teams cannot be used as bypass actors, as GitHub
    only accepts visible teams, see [Granting bypass permissions](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/creating-rulesets-for-a-repository#granting-bypass-permissions-for-your-branch-or-tag-ruleset).

## Bypass Mode

If not specified, the bypass mode will be set to `always` by default, meaning that the specified bypass actor
can bypass the restrictions of the ruleset in any case.

However, it is also possible to limit the ability to bypass the ruleset only for pull requests:

`<actor>[:<bypass-mode>]?`

| Bypass Mode    | Description                                                                      | Format                 | Example                                 |
|----------------|----------------------------------------------------------------------------------|------------------------|-----------------------------------------|
| _always_       | Allow the actor to always bypass the restrictions                                | `<actor>:always`       | `#Maintain:always`                      |
| _pull_request_ | Allow the actor to only bypass the restrictions in the context of a pull request | `<actor>:pull_request` | `@OtterdogTest/committers:pull_request` |
