A Bypass Actor represents an entity that is allowed to bypass the restrictions setup by a specific ruleset.
The following format is used to distinguish between the different types of actors that GitHub supports:

| Actor Type | Format                        | Example                    |
|------------|-------------------------------|----------------------------|
| Role       | `#<role-name>`                | `#Maintain`                |
| Team       | `@<organization>/<team-slug>` | `@OtterdogTest/committers` |
| App        | `<app-slug>`                  | `eclipse-eca-validation`   |

The following roles are currently supported:

- Write
- Maintain
- RepositoryAdmin
- OrganizationAdmin

!!! note

    Currently, GitHub does not support to specify individual users as a bypass actor for a ruleset.

# Bypass Mode

If not specified, the bypass mode will be set to `always` by default, meaning that the specified bypass actor
can bypass the restrictions of the ruleset in any case.

However, it is also possible to limit the ability to bypass the ruleset only for pull requests:

`<actor>[:<bypass-mode>]?`

| Bypass Mode    | Description                                                                      | Format                 | Example                                 |
|----------------|----------------------------------------------------------------------------------|------------------------|-----------------------------------------|
| _always_       | Allow the actor to always bypass the restrictions                                | `<actor>:always`       | `#Maintain:always`                      |
| _pull_request_ | Allow the actor to only bypass the restrictions in the context of a pull request | `<actor>:pull_request` | `@OtterdogTest/committers:pull_request` |
