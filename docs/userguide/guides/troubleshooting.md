# Troubleshooting

This page explains the messages of the validation, e.g. in the validation comment of a pull request or the output of
[`otterdog validate`](../../reference/operations/validate.md), the replies of
[`/otterdog merge`](#merging-with-otterdog-merge) when a pull request cannot be auto-merged, and the frequent
surprises of `plan` and `apply`. Click on a message to see its cause and how to fix it.

## Reading a message

The validation reports three levels of messages, the color of each of its messages below is its level:

<!-- the levels of the messages, drawn by docs/assets/theme.css -->
<div class="otterdog-outcomes" markdown>

<div class="otterdog-outcome otterdog-outcome--ko" markdown>

:material-close-circle-outline: Error

The configuration cannot be applied: the validation of the pull request fails until it is fixed.

</div>

<div class="otterdog-outcome otterdog-outcome--warn" markdown>

:material-alert-outline: Warning

The configuration can be applied, but a setting is not applied as written.

</div>

<div class="otterdog-outcome otterdog-outcome--info" markdown>

:material-information-outline: Info

A remark, e.g. a resource that is skipped, only shown with `/otterdog validate info` on a pull request, or with
`-v`.

</div>

</div>

In the messages, `<repository>` stands for the resource reported by the validation, e.g. `repository[name="my-repo"]`.
The surprises of `plan` and `apply`, which are not messages, are at the [end of the page](#plan-and-apply).

## Values of the configuration

??? failure "A value has the wrong type"

    `invalid value at '<path>': <value> is not of type '<type>'`

    **Cause**: the value does not have the type that otterdog expects, e.g. `"0"` instead of `0` for
    `required_approving_review_count`. otterdog checks the configuration against its JSON schemas before any other
    validation, and stops at such an error. Other messages of the same form report a missing property, or a property
    that is not allowed at this place.

    **Fix**: use the type of the property given in the [Reference](../../reference/index.md).

??? failure "A value is not one of the allowed ones"

    `invalid value at '<path>': '<value>' is not one of [...]`

    `<resource> has '<key>' of value '<value>', while only values (...) are allowed.`

    **Cause**: the property only accepts the listed values, e.g. `'TITLE'` instead of `'PR_TITLE'` for
    `merge_commit_title`. The first message comes from the JSON schemas, the second one from the validation of the
    resource.

    **Fix**: use one of the listed values, the Reference of the property lists the same ones.

??? warning "A property is unknown"

    `ignoring unknown properties found while validating organization config: Additional properties are not allowed
    ('<property>' was unexpected)`

    **Cause**: the property is unknown to otterdog, usually because of a typo, e.g. `has_wikki` instead of `has_wiki`.
    It has no effect. This warning is shown by the otterdog CLI, not in the validation comment of a pull request.

    **Fix**: fix its name, or remove it.

??? warning "A setting is ignored"

    `<resource> has '<key>' disabled, but '<other key>' is set to '<value>', setting will be ignored.`

    `<repository> has '<key>' enabled, while on organization level it is disabled, setting will be ignored.`

    **Cause**: the setting only applies when another one enables it, e.g. `review_dismissal_allowances` requires
    `restricts_review_dismissals`, and `selected_repositories` requires `visibility: 'selected'`. Or the organization
    restricts it for all repositories, e.g. the settings of GitHub Actions. The setting has no effect, the message is a
    warning or an info depending on the setting.

    **Fix**: remove the setting, or enable the one it depends on.

!!! tip "Catch these messages while editing"

    The Playground of the otterdog dashboard checks the same schemas while a configuration is edited: it underlines
    the invalid values and the unknown properties in the editor, and lists them when their number is clicked in its
    status. Its **Validate** button also has the configuration validated by otterdog, with limitations, see
    [Validation in the Playground](#validation-in-the-playground).

## Organization and teams

??? failure "A feature requires the enterprise plan"

    `use of organization rulesets requires an 'enterprise' plan, while this organization is currently on a '<plan>'
    plan.`

    `use of organization roles requires an 'enterprise' plan, while this organization is currently on a '<plan>'
    plan.`

    `<ruleset|policy> has 'enforcement' of value 'evaluate' which is only available for an 'enterprise' plan.`

    `enabling 'members_can_create_private_pages' requires an 'enterprise' plan.`

    **Cause**: these features are only available for organizations on the `enterprise` plan. otterdog only accepts
    organization rulesets with this plan, although GitHub also provides them with GitHub Team.

    **Fix**:

    - organization rulesets: use repository rulesets instead, see [Organization-wide rulesets](organization-rulesets.md)
    - `evaluate` of a ruleset: use `disabled` to prepare a ruleset without enforcing it, see
      [Prepare a ruleset before enforcing it](organization-rulesets.md#prepare-a-ruleset-before-enforcing-it)
    - `evaluate` of an actions policy: start with the repositories whose workflows are known, see
      [Control who and what can run workflows](github-actions.md#control-who-and-what-can-run-workflows)
    - organization roles: grant the permissions with teams instead, see [Teams and access](teams-and-access.md)
    - `members_can_create_private_pages`: keep it disabled

??? failure "A setting is required by the policies of the organization"

    `<resource> has '<key>' set to '<value>' but '<required value>' is required.`

    **Cause**: the operators of otterdog require this value for all organizations, with a validation script of
    the default configuration, see
    [Enforce settings with validation scripts](../../operating_otterdog/organization-policies.md#enforce-settings-with-validation-scripts).

    **Fix**: use the required value.

??? failure "A team is managed by another tool"

    `<team> has 'name' of value '<name>', which is not allowed due to exclusion pattern '<pattern>'.`

    **Cause**: the teams whose name matches the pattern are managed by another tool, e.g. the teams of the committers
    of a project, and otterdog does not manage them, see
    [Teams managed by another tool](../../operating_otterdog/organization-policies.md#teams-managed-by-another-tool).

    **Fix**: give the team another name. To grant an excluded team access to a repository, list it in
    `team_permissions` of the repository, see
    [Grant teams access to repositories](teams-and-access.md#grant-teams-access-to-repositories).

## Code scanning

??? failure "A language is not a CodeQL identifier"

    `invalid value at '<path>.code_scanning_default_languages[<index>]': '<language>' is not one of [...]`

    **Cause**: the value is not a CodeQL identifier, e.g. `java` or `kotlin` instead of `java-kotlin`.

    **Fix**: use one of the values listed in [Supported languages](repository-security.md#supported-languages).

??? failure "Languages are configured for a repository that does not exist yet"

    `<repository> has 'code_scanning_default_languages' configured while the repository does not yet exist.`

    **Cause**: the languages are checked against the languages detected in the repository, which requires the
    repository to exist.

    **Fix**: create the repository with default setup enabled but without languages: GitHub analyzes the languages it
    detects once code is pushed. Only configure a language in a second change if GitHub does not analyze it on its
    own, e.g. a compiled language, see [Languages analyzed by GitHub](repository-security.md#languages-analyzed-by-github).

??? failure "A language is not detected in the repository"

    `<repository> has 'code_scanning_default_languages' configured with '<language>' but this language is not
    detected in the repository. Detected languages: ...`

    **Cause**: GitHub does not detect any code of this language in the repository, e.g. `python` for a repository
    without Python code. The detected languages are listed in the message.

    **Fix**: remove the language, or configure it once the code has been pushed.

## Secrets and webhooks

??? warning "The Codespaces secrets are not available"

    `<organization_codespaces|repository_codespaces> secrets of '<org>' are not available (GitHub answers 404 for
    '<path>'), they are skipped`

    **Cause**: GitHub answers the Codespaces secrets endpoint with `404`, e.g. because Codespaces is not available for
    the organization. otterdog skips these secrets, the other secrets are not affected. This warning is shown by the
    otterdog CLI when it reads the live settings, e.g. with `plan`, `apply` or `import`. If the configuration declares
    Codespaces secrets, the operation fails instead with `declares ... secrets which cannot be managed`, as they cannot
    be compared with the live state.

    **Fix**: remove the Codespaces secrets from the configuration, or make the endpoint available. To not read
    Codespaces secrets at all, use a default configuration without `newOrgCodespacesSecret` and
    `newRepoCodespacesSecret`.

??? info "A secret or a webhook only has a dummy value"

    `<secret> only has a dummy value, resource will be skipped.`

    `<webhook> has a secret set, but only a dummy secret '********' is provided in the configuration, will be
    skipped.`

    **Cause**: the value is redacted, usually after an `import`, as GitHub never discloses secret values. otterdog
    does not change the resource.

    **Fix**: to manage the value, replace it with a reference to a credential provider, see
    [Secrets managed outside otterdog](secrets-and-variables.md#secrets-managed-outside-otterdog).

??? warning "A secret value is written in the configuration"

    `<secret> has a value '<value>' that does not use a credential provider.`

    `<webhook> has a secret '<value>' that does not use a credential provider.`

    **Cause**: the value is written in the configuration, which is stored in a repository.

    **Fix**: store it in a credential provider and reference it, see
    [Reference secret values, never write them](secrets-and-variables.md#reference-secret-values-never-write-them).

??? failure "The name of a secret or a variable is invalid"

    `<secret> starts with prefix 'GITHUB_' which is not allowed for secrets.`

    `<secret> has 'name' of value '<name>' which is not uppercase, while only uppercase names are allowed for secrets.`

    **Cause**: GitHub reserves the prefix `GITHUB_`, and normalizes the names of secrets and variables to uppercase.
    The same messages report the names of variables.

    **Fix**: rename it, e.g. `MY_TOKEN` rather than `GITHUB_TOKEN` or `my_token`.

??? failure "The organization is not allowed to use a secret"

    `<secret> references secret '<reference>' that the organization is not allowed to use: <reason>.`

    **Cause**: the operators of otterdog restrict the secrets that each organization can reference in a credential
    provider, the reason gives the allowed references. It is a warning while the restriction is not enforced, see
    [Secret access policy](../../operating_otterdog/setup.md#secret-access-policy).

    **Fix**: reference a secret of the organization, or ask the operators of otterdog to allow the reference.

??? failure "Private visibility on the free plan"

    `<secret> has 'visibility' of value 'private', which is not available for an organization with free plan.`

    **Cause**: organizations on the free plan cannot restrict organization secrets and variables to private
    repositories.

    **Fix**: use `selected` with the list of repositories instead.

## Repositories

??? warning "A public repository cannot disable forking"

    `public <repository> has 'allow_forking' disabled which is not permitted.`

    **Cause**: public repositories can always be forked.

    **Fix**: remove `allow_forking: false` from public repositories.

??? failure "The organization does not allow forking private repositories"

    `private <repository> has 'allow_forking' enabled, while the organization disables
    'members_can_fork_private_repositories'.`

    **Cause**: the organization does not allow forking private repositories.

    **Fix**: disable `allow_forking` for the repository, or allow forks in the settings of the organization.

??? warning "The wiki of a private repository requires a paid plan"

    `private <repository> has 'has_wiki' enabled, which requires at least GitHub Team billing, currently using 'free'
    plan.`

    **Cause**: wikis of private repositories require a paid GitHub plan.

    **Fix**: disable `has_wiki` for private repositories, see
    [Enable only the features that are used](repository-features.md#enable-only-the-features-that-are-used).

??? warning "The organization disables projects"

    `<repository> has 'has_projects' enabled, while the organization disables 'has_organization_projects', setting
    will be ignored.`

    **Cause**: projects are disabled for the whole organization.

    **Fix**: disable `has_projects` for the repository, or enable `has_organization_projects` for the organization.

??? warning "The organization requires a sign-off for web commits"

    `<repository> has 'web_commit_signoff_required' disabled, while the organization requires it, setting will be
    ignored.`

    **Cause**: the setting of the organization applies to all repositories, see
    [Require a sign-off for commits made in the web interface](organization-settings.md#require-a-sign-off-for-commits-made-in-the-web-interface).

    **Fix**: remove the setting from the repository.

??? failure "A topic is invalid"

    `<repository> has defined an invalid topic '<topic>'. Only lower-case, numbers and '-' are allowed characters.`

    **Cause**: topics follow the format of GitHub, e.g. `github-actions` instead of `GitHub Actions`.

    **Fix**: rename the topic, see [Describe repositories](repository-features.md#describe-repositories).

??? failure "The title and message of squash commits do not go together"

    `<repository> has ('squash_merge_commit_title', 'squash_merge_commit_message') of value (...), while only
    combinations (...) are allowed.`

    **Cause**: GitHub only accepts some combinations of the title and the message of squash and merge commits.

    **Fix**: use one of the combinations, see
    [Control the messages of merge and squash commits](pull-requests.md#control-the-messages-of-merge-and-squash-commits).

??? failure "A custom property is not defined by the organization"

    `<repository> defines an unknown custom property with key '<key>'.`

    **Cause**: a repository can only set the custom properties defined by the organization in
    `settings.custom_properties`.

    **Fix**: define the property with [newCustomProperty](../../reference/organization/custom-property.md), or fix its
    name.

??? failure "Push protection requires secret scanning"

    `<repository> has 'secret_scanning' disabled, while 'secret_scanning_push_protection' is enabled.`

    **Cause**: push protection blocks the secrets found by secret scanning, it cannot work without it.

    **Fix**: enable `secret_scanning`, or disable `secret_scanning_push_protection`, see
    [Secret scanning and push protection](repository-security.md#secret-scanning-and-push-protection).

??? failure "GitHub Pages are disabled for the site of the organization"

    `<repository> has 'gh_pages_build_type' disabled but the repo hosts the organization site and GitHub pages will be
    enabled automatically.`

    **Cause**: GitHub enables GitHub Pages for the repository `<organization>.github.io` on its own.

    **Fix**: configure GitHub Pages as given in the message, see
    [Websites with GitHub Pages](repository-patterns.md#websites-with-github-pages).

??? info "GitHub Pages without their environment"

    `<repository> hosts the organization site but no corresponding 'github-pages' environment, please add such an
    environment.`

    `<repository> has 'gh_pages_build_type' with value '<value>', but no corresponding 'github-pages' environment,
    please add such an environment.`

    **Cause**: GitHub deploys GitHub Pages through an environment named `github-pages`, which it creates on its own.
    As long as it is not in the configuration, `plan` reports it as a resource to delete.

    **Fix**: add the environment given in the message, see [GitHub Pages](environments.md#github-pages).

## Rulesets and branch protection rules

??? failure "A ruleset targets a branch without its full ref"

    `<ruleset> has an invalid 'include_refs' pattern '<pattern>', while only values ('refs/heads/*',
    '~DEFAULT_BRANCH', '~ALL') are allowed`

    **Cause**: the branches of a ruleset are matched by their full ref. The same applies to `exclude_refs`.

    **Fix**: write the full ref, e.g. `refs/heads/1.2.x` rather than `1.2.x`, or `refs/heads/release/*` for a pattern,
    and `refs/tags/` for the tags of a ruleset with `target: 'tag'`, see
    [RefMatcher](../../reference/organization/repository/ref-matcher.md).

??? failure "A rule does not apply to the ruleset"

    `<ruleset> has '<key>' set, while it is only supported by rulesets with target '<target>'.`

    `<ruleset> has '<key>' set, while it is not supported by rulesets with target 'push'.`

    `<ruleset> has '<key>' set, while it is only supported by repository rulesets.`

    `<ruleset> has 'required_workflows' set, while it is only supported by organization rulesets.`

    **Cause**: GitHub supports each rule for some rulesets only, e.g. `tag_name_pattern` for `target: 'tag'`, the push
    rules for `target: 'push'`, or `required_workflows` for organization rulesets.

    **Fix**: move the rule to a ruleset that supports it, or remove it. The Reference gives the rulesets supporting each
    rule, see [Repository Ruleset](../../reference/organization/repository/ruleset.md).

??? warning "A pattern of repositories matches no repository"

    `<ruleset> has an 'include_repo_names' pattern '<pattern>' that does not match any existing repository`

    **Cause**: no repository of the organization matches the pattern of an organization ruleset, usually because of a
    typo, or because the repository does not exist yet. The same applies to `exclude_repo_names`.

    **Fix**: fix the pattern, see [Target repositories by name](organization-rulesets.md#target-repositories-by-name).

??? failure "Push rules on a public repository"

    `<ruleset> has 'restricted_file_paths' set, while push rules are only supported by private and internal
    repositories.`

    **Cause**: GitHub rejects the push rules, e.g. `restricted_file_paths` or `max_file_size`, of a ruleset of a public
    repository when the ruleset is applied, whatever the plan of the organization. Push rulesets also require at least
    GitHub Team.

    **Fix**: remove the push ruleset, or make the repository private, see
    [Restrict the files that can be pushed](branch-protection.md#restrict-the-files-that-can-be-pushed).

??? failure "The required deployment environment is not in the repository"

    `<ruleset> requires deployment environment '<environment>' which is not defined in the repository itself.`

    **Cause**: a ruleset or branch protection rule that requires a successful deployment can only reference an
    environment of the same repository.

    **Fix**: define the environment in the repository, see
    [Require a successful deployment before merging](environments.md#require-a-successful-deployment-before-merging).

## Actions policies

??? failure "The workflows of a policy are invalid"

    `<policy> has empty 'include_workflows' and 'exclude_workflows', while at least one pattern is required, use
    '~ALL' to target all workflows.`

    `<policy> has 'include_workflows' combining '~ALL' with other patterns, while '~ALL' must be used on its own.`

    `<policy> has '~ALL' in 'exclude_workflows', while it is only allowed in 'include_workflows'.`

    **Cause**: a policy targets the workflows matching `include_workflows`, except the ones matching
    `exclude_workflows`, and needs at least one pattern. `~ALL`, which targets all the workflows, is only allowed on
    its own in `include_workflows`.

    **Fix**: use `~ALL` on its own, or list the workflow files, e.g. `.github/workflows/release.yml`, see
    [Control who and what can run workflows](github-actions.md#control-who-and-what-can-run-workflows).

??? failure "An allowed actor is invalid"

    `<policy> has an invalid allowed actor '<actor>', only users or bots ('@<login>'), teams ('@<org>/<team-slug>'),
    roles ('#<role>'), apps ('<app-slug>') or actors referenced by their type and id ('<type>:<id>') are supported.`

    `<policy> has allowed actor '<actor>' with unknown role '<role>', only roles ('RepositoryAdmin' | 'Write' |
    'Maintain' | 'OrganizationAdmin') or the id of a custom role are supported.`

    `<policy> has allowed actor '<actor>' with unknown type '<type>', only types (<types>) are supported.`

    **Cause**: an actor of `allowed_actors` is written like a bypass actor of a ruleset: `@` and the login for a user
    or a bot, `@` and the slug with the organization for a team, `#` for a role, the slug alone for an app. An email
    address, e.g. `alice@example.org`, or a role that GitHub does not provide, e.g. `#Read`, is rejected.

    **Fix**: fix the actor, see [AllowedActor](../../reference/organization/repository/allowed-actor.md).

??? warning "A policy does not require any rule"

    `<policy> does not require any rule, set one of ('allowed_actors' | 'allowed_events').`

    **Cause**: `allowed_actors` and `allowed_events` are both `null`, their default value, which does not require the
    rule: the policy blocks nothing.

    **Fix**: set the actors or the events allowed to run the targeted workflows, see
    [Control who and what can run workflows](github-actions.md#control-who-and-what-can-run-workflows).

??? warning "A policy blocks all the targeted workflows"

    `<policy> has an empty 'allowed_actors', no actor is allowed to run the targeted workflows.`

    `<policy> has an empty 'allowed_events', no event is allowed to trigger the targeted workflows.`

    **Cause**: an empty list allows nothing, unlike `null`, which does not require the rule.

    **Fix**: list the allowed actors or events, or set the rule to `null`.

??? warning "An event is unknown"

    `<policy> has 'allowed_events' containing unknown event '<event>', GitHub might reject it.`

    **Cause**: the event is not a trigger of workflows known to otterdog, usually because of a typo, or because it is
    an activity type, e.g. `pull_request_closed` instead of `pull_request`.

    **Fix**: use the name of the event, see
    [Events that trigger workflows](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows).

??? warning "An organization policy targets no repository"

    `<policy> has an empty 'include_repo_names', the policy does not apply to any repository, use '~ALL' to target
    all repositories.`

    `<policy> has an 'include_repo_names' pattern '<pattern>' that does not match any existing repository`

    `<policy> has 'protect_repo_names' set to 'True' but 'include_repo_names' and 'exclude_repo_names' are empty.`

    **Cause**: `newOrgActionsPolicy` targets no repository by default, its `include_repo_names` is empty. A pattern can
    also match no repository, usually because of a typo, or because the repository does not exist yet. The same
    applies to `exclude_repo_names`.

    **Fix**: list the repositories in `include_repo_names`, or use `~ALL` to target all of them, see
    [Control who and what can run workflows](github-actions.md#control-who-and-what-can-run-workflows).

??? warning "An organization policy targets repositories by custom property or id"

    `actions policy '<name>' targets repositories by <repository_property|repository_id>, which is not supported, its
    targeting is kept on update`

    **Cause**: the policy was created in the GitHub web interface with a targeting that otterdog does not support.
    otterdog keeps this targeting when it updates the policy, and does not compare its `include_repo_names`,
    `exclude_repo_names` and `protect_repo_names`. This warning is shown by the otterdog CLI when it reads the live
    settings, e.g. with `plan`, `apply` or `import`.

    **Fix**: nothing, to keep this targeting, see [Unsupported settings](../unsupported.md). To manage the targeting
    with otterdog, target the repositories by name in the web interface first.

??? warning "A policy with the same name already exists"

    `actions policy '<name>' already exists for org '<org>', updating it`

    `actions policy '<name>' already exists for repo '<org>/<repo>', updating it`

    **Cause**: GitHub does not allow two policies with the same name. When the configuration adds a policy whose name
    is used by a policy it did not know, e.g. created in the web interface or by a previous apply that failed,
    otterdog updates that policy instead. This warning is shown in the log of the apply.

    **Fix**: nothing, the policy is updated as configured.

## Merging with `/otterdog merge`

When a pull request cannot be auto-merged, `/otterdog merge` replies with a warning listing the
[conditions of the auto-merge](../workflow.md#can-my-pull-request-be-auto-merged) that are not met, in this order.

??? warning "The pull request is closed"

    `pull request is <closed|merged>, only open pull requests can be managed`

    **Cause**: only an open pull request can be merged.

    **Fix**: reopen a closed pull request. A merged pull request is applied, see [Apply](../workflow.md#5-apply).

??? warning "The pull request is a draft"

    `pull request is a draft, mark it as ready for review first`

    **Cause**: a draft is not merged, even once validated with `/otterdog validate`.

    **Fix**: mark the pull request as ready for review: it is validated again. Then comment `/otterdog merge` again.

??? warning "The pull request is not validated yet"

    `pull request has not been validated yet, run /otterdog validate first`

    **Cause**: the validation did not run, e.g. it failed before evaluating the configuration.

    **Fix**: comment `/otterdog validate`. Then comment `/otterdog merge` again.

??? warning "The latest commit is not validated yet"

    `the latest commit of the pull request has not been validated yet, wait for its validation or run /otterdog
    validate`

    **Cause**: a commit has been pushed since the last validation: its validation is still running, or the
    validation of a previous commit completed after it.

    **Fix**: wait for the validation comment of the latest commit, or comment `/otterdog validate`. Then comment
    `/otterdog merge` again.

??? warning "The pull request is not valid"

    `pull request is not valid, check the /otterdog validate comment for details and push a fix`

    **Cause**: the last validation found errors.

    **Fix**: fix the errors listed in the validation comment, see their messages on this page, and push: the pull
    request is validated again.

??? warning "It is unknown whether the pull request can be auto-merged"

    `it has not been checked whether the pull request supports auto merge`

    **Cause**: the last validation did not record whether the changes can be auto-merged.

    **Fix**: comment `/otterdog validate`, then `/otterdog merge` again.

??? warning "The changes need an admin"

    `pull request cannot be automatically merged (contains secrets, requires web UI changes, may incur costs,
    includes deletions or touches non-configuration files)`

    **Cause**: the pull request contains changes that otterdog does not apply on its own, the validation comment lists
    them.

    **Fix**: a member of the admin teams reviews and merges the pull request. To have the rest auto-merged, move these
    changes to a pull request of their own, see
    [Changes that prevent the auto-merge](../workflow.md#changes-that-prevent-the-auto-merge).

??? warning "Neither the author nor an approval allows the auto-merge"

    `The author is not a member of an approval or admin team`

    `No approval from a member of an approval or admin team <has been submitted yet|was found>`

    **Cause**: the auto-merge requires an author or an approval from a member of these teams, the pull request has
    neither. The reply lists the teams in its section **Approval and admin teams**.

    **Fix**: ask a member of an approval team for a review, then comment `/otterdog merge` again: otterdog checks the
    approvals again.

??? warning "The teams of the author are unknown"

    `The author's team membership is unknown (comment /otterdog team-info on the pull request to refresh it)`

    **Cause**: otterdog has not retrieved the teams of the author, e.g. because the retrieval failed. It retrieves them
    when the pull request is opened or marked as ready for review, and at each validation while they are unknown. It
    never does for a bot, whose pull requests need an approval.

    **Fix**: comment `/otterdog team-info` or `/otterdog validate`, then `/otterdog merge` again.

??? warning "The comment comes from someone who cannot merge"

    `Only the author of the pull request, or a member of an approval team or of an admin team, is allowed to
    auto-merge.`

    **Cause**: `/otterdog merge` was commented by someone else than the author, who is not a member of an approval or
    admin team.

    **Fix**: let the author, or a member of these teams, comment `/otterdog merge`.

??? question "Nothing happens after `/otterdog merge`"

    **Cause**: the comment does not start with the command, or GitHub refused the merge, e.g. because of a conflict
    with `main`, or because a commit has been pushed after the validated one.

    **Fix**: start the comment with `/otterdog merge`. Otherwise, update the branch with `main` if it conflicts, wait
    for the validation of the latest commit, and comment `/otterdog merge` again.

## Plan and apply

??? question "`plan` shows changes that nobody made in the configuration"

    **Cause**: the configuration of the organization only contains the differences to its default configuration. A
    change of the default configuration, or a setting changed in the GitHub web interface, shows up in `plan`.

    **Fix**: see [Inherited and explicit values](inheritance.md).

??? question "A ruleset, branch protection rule or actions policy created in the GitHub web interface is deleted"

    **Cause**: otterdog manages all the protections and actions policies of the organization and of the configured
    repositories, one that is not part of the configuration is removed when deletions are applied.

    **Fix**: add it to the configuration instead, see the warning in
    [Otterdog specifics](rulesets-vs-branch-protection.md#otterdog-specifics).

??? question "A language removed from `code_scanning_default_languages` is still analyzed"

    **Cause**: the configured languages are the minimum set of languages to analyze: the languages that GitHub
    analyzes in addition are kept, and `plan` does not report them.

    **Fix**: to stop analyzing a language, change the default setup in the GitHub web interface, see
    [Languages analyzed by GitHub](repository-security.md#languages-analyzed-by-github).

??? question "A rotated secret is not updated on GitHub"

    **Cause**: otterdog cannot detect that the value of a credential changed in the credential provider.

    **Fix**: update the secret explicitly, see [Updating secret values](secrets-and-variables.md#updating-secret-values).

??? question "Changes to some organization settings are not applied automatically"

    **Cause**: some settings, e.g. `members_can_create_teams` or the discussions of the organization, can only be
    changed through the GitHub web interface, which requires the credentials of a user that can log in to GitHub.
    `plan` and `apply` skip them with `--no-web-ui`.

    **Fix**: such changes merged in a pull request of the configuration repository are applied manually by an admin,
    see [Restrict what members can do](organization-settings.md#restrict-what-members-can-do).

??? question "Loading a page of the GitHub web interface times out"

    `Page.goto: Timeout 10000ms exceeded`

    **Cause**: the settings only available through the GitHub web interface are retrieved with a headless browser,
    which waits up to 10 seconds for a page to load, too short on a slow connection.

    **Fix**: increase the timeout, in milliseconds, with the environment variable `OTTERDOG_WEB_TIMEOUT`, e.g.
    `export OTTERDOG_WEB_TIMEOUT=60000`, or skip these settings with `--no-web-ui`, see
    [Environment variables](../../operating_otterdog/setup.md#environment-variables).

## Validation in the Playground

The **Validate** button of the Playground of the otterdog dashboard has the configuration of an organization, created
by `orgs.newOrg(...)`, validated by otterdog on the server, with the default configuration of the Playground. The
button is not shown for a snippet, e.g. creating a repository, and is disabled for a configuration failing to evaluate
or having schema errors. The evaluated configuration is only sent to the server when the button is clicked, it is
neither stored nor applied.

A configuration without problem in the Playground can still be rejected by the validation of its pull request:

<!-- what the Playground and the pull request check, drawn by docs/assets/theme.css -->
<div class="otterdog-outcomes" markdown>

<div class="otterdog-outcome otterdog-outcome--ok" markdown>

:material-code-braces: The Playground checks

- the **schemas** while you edit: the types, the allowed values and the unknown properties
- with **Validate**, the messages of `validate` listed on this page, the infos included, at the property they are
  about, otherwise at the repository or the organization
- with **Propose on GitHub**, the same validation first: it asks to confirm before proposing a configuration with
  errors, or that cannot be validated

</div>

<div class="otterdog-outcome otterdog-outcome--warn" markdown>

:material-source-pull: Only the pull request checks

- the **validations depending on GitHub**: the members of a team with `skip_non_organization_members` being members
  of the organization, and the languages of `code_scanning_default_languages` being detected in the repository
- the **plan**: whether the changes require secrets, settings of the Web UI, or remove resources, which prevents the
  auto-merge. The Playground of a project shows the changes to the current configuration, though
- the **comparison with GitHub**, like `/otterdog check-sync`
- the **default configuration of your organization**: the global Playground validates with its own, use the
  Playground of your project instead

</div>

</div>

Some checks are only done when the changes are applied, by `validate` neither: the teams, users and apps of
`bypass_actors` and of `allowed_actors` must exist, and GitHub can reject a value that otterdog accepts.
