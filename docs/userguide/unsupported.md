# Unsupported settings

otterdog manages the resources and settings documented in the [Reference](../reference/index.md). The features of
GitHub below are not supported, the list is not exhaustive.

otterdog leaves what it does not support untouched: neither the validation of a pull request nor the sync check
reports it, and applying a change never overwrites it. Change these settings directly on GitHub, or ask the
administrators of your organization to do it.

<div class="grid cards" markdown>

-   :material-domain:{ .lg .middle } **Organization**

    ---

    - the **profile picture** [#119](https://github.com/eclipse-csi/otterdog/issues/119)
    - the **pinned repositories**
    - the **default labels** of new repositories
    - the policies of **GitHub Apps and OAuth apps**
    - the **membership**: inviting members and choosing the owners. otterdog manages the members of the
      [teams](../reference/organization/team/index.md), who must already be members of the organization.

-   :material-source-repository:{ .lg .middle } **Repositories**

    ---

    - the **social media preview** [#119](https://github.com/eclipse-csi/otterdog/issues/119)
    - the **releases, packages and deployments** shown on the main page
    - the **autolink references**
    - the **individual collaborators**: use teams and `team_permissions` instead
    - the **transfer** to another organization

-   :material-shield-lock-outline:{ .lg .middle } **Rules and protection**

    ---

    - the **merge queue** of a branch protection rule [#86](https://github.com/eclipse-csi/otterdog/issues/86): use
      the `required_merge_queue` of a [ruleset](../reference/organization/repository/ruleset.md) instead
    - the **rules and parameters of rulesets** other than the ones listed in
      [Otterdog specifics](guides/rulesets-vs-branch-protection.md#otterdog-specifics), e.g. the required reviewers
      of the rule requiring a pull request
    - targeting the repositories of an organization ruleset by **custom properties**
    - **deploy keys** as bypass actors of a ruleset
    - ~~tag protections~~, deprecated by GitHub [#143](https://github.com/eclipse-csi/otterdog/issues/143): use
      rulesets instead, see [Protecting tags and releases](guides/tag-protection.md)

-   :material-cog-play-outline:{ .lg .middle } **GitHub Actions and Copilot**

    ---

    - the **Require lockfile** rule of [actions policies](../reference/organization/actions-policy.md): GitHub does
      not provide it in its API yet, otterdog keeps it when it updates a policy
      [#945](https://github.com/eclipse-csi/otterdog/issues/945)
    - targeting the repositories of an organization actions policy by **custom properties or ids**: otterdog keeps
      this targeting when it updates a policy
    - the **actions policies of an enterprise**
    - the **custom deployment protection rules** of environments, provided by GitHub Apps
    - the **secrets and variables of Copilot agents**

</div>

!!! info "Supported, but applied by an admin"

    Some settings are supported but only available in the web interface of GitHub, e.g. `members_can_create_teams`
    or `has_discussions` of the [organization settings](../reference/organization/settings.md). A pull request
    changing them cannot be auto-merged, an admin applies it, see
    [Changes that prevent the auto-merge](workflow.md#changes-that-prevent-the-auto-merge). The Reference marks the
    settings that otterdog can only read, e.g. `two_factor_requirement`.

!!! tip "Missing a feature?"

    Open an [issue](https://github.com/eclipse-csi/otterdog/issues/new?template=Blank+issue) to ask for the support of
    a feature of GitHub.
