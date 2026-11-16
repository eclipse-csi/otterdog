# Adding, renaming and removing resources

Every resource of an organization, e.g. a repository, a team or a webhook, is declared in `otterdog/<org>.jsonnet`.
To add, rename or remove one, change its declaration and propose the change with a pull request, see
[Workflow for changes](workflow.md).

## TL;DR

<!-- what each change does, drawn by docs/assets/theme.css -->
<div class="otterdog-outcomes" markdown>

<div class="otterdog-outcome otterdog-outcome--ok" markdown>

:material-plus-circle-outline: Add

Declare the resource with its `orgs.new…` function at its place, with only the values that differ from the default
configuration.

:material-check-decagram-outline: Auto-merge, except for secrets and private repositories.

[:material-arrow-right: Adding a resource](#adding-a-resource)

</div>

<div class="otterdog-outcome" markdown>

:material-rename-outline: Rename

Change the name of a repository or the URL of a webhook, and list the previous one in `aliases`. Otherwise, the
resource is deleted and created again.

:material-check-decagram-outline: Auto-merge with `aliases`.

[:material-arrow-right: Renaming a resource](#renaming-a-resource)

</div>

<div class="otterdog-outcome otterdog-outcome--ko" markdown>

:material-delete-outline: Remove

Delete its declaration: once merged, otterdog deletes the resource on GitHub, a repository with all its content.

:material-account-group-outline: Always merged by an admin.

[:material-arrow-right: Removing a resource](#removing-a-resource)

</div>

</div>

## How otterdog recognizes a resource

otterdog matches the resources of the configuration with the ones on GitHub by their identifier, e.g. the name of a
repository or the URL of a webhook. Whether the identifier matches decides what the change does:

<!-- how otterdog matches the resources, drawn by docs/assets/theme.css -->
<div class="otterdog-match" markdown>

<div class="otterdog-match__row otterdog-match__row--head" markdown>
<span>:material-file-code-outline: Configuration</span><span>Validation</span><span>:material-github: GitHub</span>
</div>

<div class="otterdog-match__row" markdown>
<span class="otterdog-match__config">`newRepo('website')`</span><span class="otterdog-match__result"><span>~ modify</span></span><span class="otterdog-match__github">`website`: only what differs changes</span>
</div>

<div class="otterdog-match__row otterdog-match__row--create" markdown>
<span class="otterdog-match__config">`newRepo('new-tool')`</span><span class="otterdog-match__result"><span>+ create</span></span><span class="otterdog-match__github otterdog-match__none">no `new-tool` yet</span>
</div>

<div class="otterdog-match__row" markdown>
<span class="otterdog-match__config">`newRepo('docs')` with `aliases: ['documentation']`</span><span class="otterdog-match__result"><span>~ rename</span></span><span class="otterdog-match__github">`documentation`: renamed to `docs`</span>
</div>

<div class="otterdog-match__row otterdog-match__row--delete" markdown>
<span class="otterdog-match__config otterdog-match__none">`old-lib` removed by the pull request</span><span class="otterdog-match__result"><span>- delete</span></span><span class="otterdog-match__github">`old-lib`: deleted</span>
</div>

</div>

A resource is only deleted when a pull request removes it from the configuration. The identifier of each resource:

| Resource                                                                  | Identifier               |
|---------------------------------------------------------------------------|--------------------------|
| Repository                                                                | `name`, and its `aliases` |
| Webhook of the organization or of a repository                            | `url`, and its `aliases`  |
| Team, organization role, custom property, code security configuration    | `name`                   |
| Secret (Actions, Dependabot, Codespaces), variable, environment, ruleset  | `name`                   |
| Branch protection rule                                                    | `pattern`                |
| IdP group connected to a team (`team_sync`)                               | `id`                     |

## Adding a resource

Declare the resource with the function of the default configuration at its place in the configuration:

<!-- where the resources are declared, drawn by docs/assets/theme.css -->
<div class="otterdog-tree" markdown>

- **orgs.newOrg**
    - **settings.custom_properties** [newCustomProperty](../reference/organization/custom-property.md)
    - **roles** [newOrgRole](../reference/organization/role.md)
    - **teams** [newTeam](../reference/organization/team/index.md)
        - **team_sync** [newTeamSync](../reference/organization/team/team-sync.md)
    - **webhooks** [newOrgWebhook](../reference/organization/webhook.md)
    - **secrets** [newOrgSecret](../reference/organization/secret.md)
    - **dependabot_secrets** [newOrgDependabotSecret](../reference/organization/dependabot-secret.md)
    - **codespaces_secrets** [newOrgCodespacesSecret](../reference/organization/codespaces-secret.md)
    - **variables** [newOrgVariable](../reference/organization/variable.md)
    - **rulesets** [newOrgRuleset](../reference/organization/ruleset.md)
    - **code_security_configurations** [newOrgCodeSecurityConfiguration](../reference/organization/code-security-configuration.md)
    - **_repositories** [newRepo](../reference/organization/repository/index.md) [extendRepo](../reference/organization/repository/index.md#jsonnet-function)
        - **webhooks** [newRepoWebhook](../reference/organization/repository/webhook.md)
        - **secrets** [newRepoSecret](../reference/organization/repository/secret.md)
        - **dependabot_secrets** [newRepoDependabotSecret](../reference/organization/repository/dependabot-secret.md)
        - **codespaces_secrets** [newRepoCodespacesSecret](../reference/organization/repository/codespaces-secret.md)
        - **variables** [newRepoVariable](../reference/organization/repository/variable.md)
        - **branch_protection_rules** [newBranchProtectionRule](../reference/organization/repository/branch-protection-rule.md)
        - **rulesets** [newRepoRuleset](../reference/organization/repository/ruleset.md)
        - **environments** [newEnvironment](../reference/organization/repository/environment/index.md)
            - **secrets** [newEnvSecret](../reference/organization/repository/environment/secret.md)
            - **variables** [newEnvVariable](../reference/organization/repository/environment/variable.md)

</div>

The rules of a ruleset have their own functions too, they are the values of the keys of the ruleset:

<!-- the rules of a ruleset, drawn by docs/assets/theme.css -->
<div class="otterdog-tree" markdown>

- **rulesets** [newOrgRuleset](../reference/organization/ruleset.md) [newRepoRuleset](../reference/organization/repository/ruleset.md)
    - **required_pull_request** [newPullRequest](../reference/organization/repository/ruleset.md#pull-request-settings)
    - **required_status_checks** [newStatusChecks](../reference/organization/repository/ruleset.md#status-check-settings)
    - **required_merge_queue** [newMergeQueue](../reference/organization/repository/ruleset.md#merge-queue-settings)
    - **copilot_code_review** [newCopilotCodeReview](../reference/organization/repository/ruleset.md#copilot-code-review-settings)
    - **required_code_scanning** [newCodeScanning](../reference/organization/repository/ruleset.md#code-scanning-settings)
    - **required_code_quality** [newCodeQuality](../reference/organization/repository/ruleset.md#code-quality-settings) <span class="otterdog-tree__note">repository rulesets only</span>
    - **required_code_coverage** [newCodeCoverage](../reference/organization/repository/ruleset.md#code-coverage-settings) <span class="otterdog-tree__note">repository rulesets only</span>
    - **required_workflows** [newWorkflows](../reference/organization/ruleset.md#workflows-settings) <span class="otterdog-tree__note">organization rulesets only</span>
    - **commit_message_pattern** [newPattern](../reference/organization/repository/ruleset.md#pattern-settings)
    - **commit_author_email_pattern** [newPattern](../reference/organization/repository/ruleset.md#pattern-settings)
    - **committer_email_pattern** [newPattern](../reference/organization/repository/ruleset.md#pattern-settings)
    - **branch_name_pattern** [newPattern](../reference/organization/repository/ruleset.md#pattern-settings)
    - **tag_name_pattern** [newPattern](../reference/organization/repository/ruleset.md#pattern-settings)

</div>

Each function and its properties are documented in the [Reference](../reference/organization/index.md), e.g.
[Repository](../reference/organization/repository/index.md). The new resource inherits all the values of the
default configuration: only declare the ones that differ, see
[Inherited and explicit values](guides/inheritance.md).

For example, to add a repository `new-repo` next to an existing one:

``` diff
 orgs.newOrg('my-project', 'my-org') {
   _repositories+:: [
     orgs.newRepo('existing-repo') {
       description: "My first repository",
     },
+    orgs.newRepo('new-repo') {
+      description: "My second repository",
+      allow_merge_commit: false,
+      dependabot_alerts_enabled: false,
+    },
   ],
 }
```

!!! tip "Try it in the Playground"

    The Playground of the dashboard shows the resulting resource with the values of the default configuration, and
    can propose the change as a pull request, see [Prepare your change](workflow.md#1-prepare-your-change).

!!! note "A repository defined by the default configuration"

    Use `orgs.extendRepo('<name>')` instead of `orgs.newRepo('<name>')` to change a repository that the default
    configuration already defines: `orgs.newRepo` would reset the values it customized.

Some properties are only used when the repository is created, e.g. `template_repository` or `forked_repository` to
create it from a template or as a fork, see [Common repository patterns](guides/repository-patterns.md).

### What it means for the merge

<!-- what an addition means for the merge, drawn by docs/assets/theme.css -->
<div class="otterdog-outcomes" markdown>

<div class="otterdog-outcome otterdog-outcome--ok" markdown>

:material-check-decagram-outline: Auto-merge, once approved

A public repository, a team, a variable, a ruleset, an environment, or a webhook without secret.

</div>

<div class="otterdog-outcome otterdog-outcome--admin" markdown>

:material-key-variant: An admin applies the secret

A secret (Actions, Dependabot or Codespaces), or a webhook with a secret: an admin merges the pull request and
applies the secret.

</div>

<div class="otterdog-outcome otterdog-outcome--warn" markdown>

:material-currency-usd: An admin checks the costs

A private repository, or one with a GitHub Actions cache above the free limit.

</div>

</div>

See [Changes that prevent the auto-merge](workflow.md#changes-that-prevent-the-auto-merge).

## Renaming a resource

Changing the identifier of a resource, e.g. the name of a repository, does not rename it: otterdog no longer finds
the resource with its previous identifier on GitHub, deletes it and creates a new one. For a repository or a webhook,
`aliases` keeps it:

<!-- a renaming without and with aliases, drawn by docs/assets/theme.css -->
<div class="otterdog-lane otterdog-lane--ko" markdown>

<div class="otterdog-lane__title" markdown>:material-close-circle-outline: Without `aliases`</div>

<div class="otterdog-match" markdown>

<div class="otterdog-match__row otterdog-match__row--create" markdown>
<span class="otterdog-match__config">`newRepo('new-name')`</span><span class="otterdog-match__result"><span>+ create</span></span><span class="otterdog-match__github otterdog-match__none">no `new-name`: a new, empty repository</span>
</div>

<div class="otterdog-match__row otterdog-match__row--delete" markdown>
<span class="otterdog-match__config otterdog-match__none">no `old-name` any more</span><span class="otterdog-match__result"><span>- delete</span></span><span class="otterdog-match__github">`old-name`: deleted with its issues, pull requests and wiki</span>
</div>

</div>

</div>

<div class="otterdog-lane otterdog-lane--ok" markdown>

<div class="otterdog-lane__title" markdown>:material-check-circle-outline: With `aliases: ['old-name']`</div>

<div class="otterdog-match" markdown>

<div class="otterdog-match__row" markdown>
<span class="otterdog-match__config">`newRepo('new-name')` with `aliases: ['old-name']`</span><span class="otterdog-match__result"><span>~ rename</span></span><span class="otterdog-match__github">`old-name`: renamed, with all its content</span>
</div>

</div>

</div>

!!! danger "Never rename a repository without `aliases`"

    The validation of the pull request shows the repository as removed and added again. Such a pull request cannot
    be auto-merged, but once merged, the repository is deleted with its content, which otterdog cannot restore.

### Repositories and webhooks: `aliases`

List the previous identifiers of the resource in `aliases`:

=== ":material-source-repository: Repository"

    ``` jsonnet
    orgs.newRepo('new-name') {
      aliases: ['old-name'],
      description: "My repository",
    },
    ```

    The validation of the pull request then shows a renaming instead of a deletion, which can be auto-merged:

    ``` diff
    ~ repository[name="new-name"] {
    ~   name = "old-name" -> "new-name"
    ~ }
    ```

=== ":material-webhook: Webhook"

    ``` jsonnet
    orgs.newOrgWebhook('https://ci.example.org/hooks/github') {
      aliases: ['https://ci.example.org/github-webhook/'],
      events+: [
        "push",
      ],
    },
    ```

    The existing webhook keeps its deliveries and settings, only its URL changes. A webhook with a `secret` is
    applied by an admin, see [Change the URL of a webhook](guides/webhooks.md#change-the-url-of-a-webhook).

Once the change is applied, `aliases` is no longer needed. You can keep it to record the previous identifiers of the
resource.

### The other resources

The other resources are deleted and created again when their identifier changes. Their settings come from the
configuration, but what otterdog does not manage is lost, e.g. the deployment history of an environment. As the pull
request removes a resource, an admin merges it.

## Removing a resource

Delete the declaration of the resource from the configuration. For example, to remove a webhook of the
organization:

``` diff
 orgs.newOrg('my-project', 'my-org') {
   webhooks+: [
-    orgs.newOrgWebhook('https://ci.example.org/github-webhook/') {
-      events+: [
-        "pull_request",
-        "push",
-      ],
-    },
   ],
 }
```

<!-- the removal of a resource, drawn by docs/assets/theme.css -->
<div class="otterdog-flow" markdown>

<div class="otterdog-flow__step" markdown>

:material-source-pull:{ .otterdog-flow__icon }

**Pull request**

Removes the declaration of the resource.

</div>

<div class="otterdog-flow__step" markdown>

:material-shield-check-outline:{ .otterdog-flow__icon }

**Validation**

Shows the resource as removed, no auto-merge.

</div>

<div class="otterdog-flow__step" markdown>

:material-account-group-outline:{ .otterdog-flow__icon .otterdog-flow__icon--admin }

**Admin**

Reviews and merges the pull request.

</div>

<div class="otterdog-flow__step" markdown>

:material-delete-outline:{ .otterdog-flow__icon .otterdog-flow__icon--danger }

**Deletion**

otterdog deletes the resource on GitHub.

</div>

</div>

A pull request that removes a resource is never auto-merged: a member of the admin teams reviews and merges it. Only
the resources that the pull request removes from the configuration are deleted, the other resources of GitHub are
left untouched.

!!! warning "Removing a repository deletes it, with its content"

    Its issues, pull requests and wiki are deleted, otterdog cannot restore them. Prefer archiving the repository
    with `archived: true`, see [Renaming, archiving and deleting](guides/repository-patterns.md#renaming-archiving-and-deleting).

!!! note "A resource inherited from the default configuration"

    A resource that the default configuration declares is not in your configuration: to remove it, replace the
    inherited list instead of extending it, i.e. `rulesets: [...]` instead of `rulesets+: [...]`, see
    [Extending or replacing values](guides/inheritance.md#extending-or-replacing-values).
