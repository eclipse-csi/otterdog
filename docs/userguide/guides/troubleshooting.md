# Troubleshooting

This page lists frequent messages of [`validate`](../../reference/operations/validate.md) and frequent surprises of
`plan` and `apply`, with their cause and how to address them. `validate` reports three levels of messages:

- **Error**: the configuration cannot be applied, it must be fixed.
- **Warning**: the configuration can be applied, but a setting will not be applied as specified.
- **Info**: a remark, only shown with `-v`, e.g. a resource that will be skipped.

In the messages below, `<repository>` stands for the resource reported by `validate`, e.g.
`repository[name="my-repo"]`.

## Values of the configuration

**`invalid value at '<path>': <value> is not of type '<type>'`**

: A value does not have the type that otterdog expects, e.g. `"0"` instead of `0` for
  `required_approving_review_count`. Otterdog checks the configuration against its JSON schemas before any other
  validation, and stops at such an error. Other messages of the same form report a missing property, or a property
  that is not allowed at this place.

**`invalid value at '<path>': '<value>' is not one of [...]`**

: The property only accepts the listed values, e.g. `'TITLE'` instead of `'PR_TITLE'` for `merge_commit_title`. The
  reference of the property lists the same values.

**`ignoring unknown properties found while validating organization config: Additional properties are not allowed ('<property>' was unexpected)`** (Warning)

: The property is unknown to otterdog, usually because of a typo, e.g. `has_wikki` instead of `has_wiki`, and has no
  effect. Fix its name or remove it.

## Code scanning

**`invalid value at '<path>.code_scanning_default_languages[<index>]': '<language>' is not one of [...]`**

: The value is not a CodeQL identifier, e.g. `java` or `typescript` instead of `java-kotlin` or
  `javascript-typescript`. Use one of the values listed in
  [Supported languages](repository-security.md#supported-languages).

**`<repository> has 'code_scanning_default_languages' configured while the repository does not yet exist.`**

: Languages are checked against the languages detected in the repository, which requires the repository to exist.
  Create the repository first, with default setup enabled but without languages, then configure the languages in a
  second change, see [Languages must be detected in the repository](repository-security.md#languages-must-be-detected-in-the-repository).

**`<repository> has 'code_scanning_default_languages' configured with '<language>' but this language is not detected in the repository. Detected languages: ...`**

: GitHub does not detect any code of this language in the repository, e.g. `python` for a repository without Python
  code. Remove the language, or configure it once the code has been pushed. The detected languages are listed in
  the message.

## Secrets and webhooks

**`<secret> only has a dummy value, resource will be skipped.`** (Info)
**`<webhook> has a secret set, but only a dummy secret '********' is provided in the configuration, will be skipped.`** (Info)

: The value is redacted, usually after an `import`, as GitHub never discloses secret values. The resource is not
  changed by otterdog. Replace the value with a reference to a credential provider to manage it, see
  [Secrets managed outside otterdog](secrets-and-variables.md#secrets-managed-outside-otterdog).

**`<secret> has a value '<value>' that does not use a credential provider.`** (Warning)

: The value is written in the configuration, which is stored in a repository. Store it in a credential provider and
  reference it, see [Reference secret values, never write them](secrets-and-variables.md#reference-secret-values-never-write-them).

**`<secret> has 'visibility' of value 'private', which is not available for an organization with free plan.`**

: Organizations on the free plan cannot restrict organization secrets and variables to private repositories. Use
  `selected` with the list of repositories instead.

## Repositories

**`public <repository> has 'allow_forking' disabled which is not permitted.`** (Warning)

: Public repositories can always be forked. Remove `allow_forking: false` from public repositories.

**`private <repository> has 'allow_forking' enabled, while the organization disables 'members_can_fork_private_repositories'.`**

: The organization does not allow forking private repositories. Disable `allow_forking` for the repository, or
  allow forks in the settings of the organization.

**`private <repository> has 'has_wiki' enabled, which requires at least GitHub Team billing, currently using 'free' plan.`** (Warning)

: Wikis of private repositories require a paid GitHub plan. Disable `has_wiki` for private repositories, see
  [Enable only the features that are used](repository-features.md#enable-only-the-features-that-are-used).

**`<repository> has 'has_projects' enabled, while the organization disables 'has_organization_projects', setting will be ignored.`** (Warning)

: Projects are disabled for the whole organization. Disable `has_projects` for the repository, or enable
  `has_organization_projects` for the organization.

**`<repository> has 'web_commit_signoff_required' disabled, while the organization requires it, setting will be ignored.`** (Warning)

: The setting of the organization applies to all repositories, see
  [Require a sign-off for commits made in the web interface](organization-settings.md#require-a-sign-off-for-commits-made-in-the-web-interface).
  Remove the setting from the repository.

**`<repository> has defined an invalid topic '<topic>'. Only lower-case, numbers and '-' are allowed characters.`**

: Topics follow the format of GitHub, e.g. `github-actions` instead of `GitHub Actions`, see
  [Describe repositories](repository-features.md#describe-repositories).

**`<repository> has ('squash_merge_commit_title', 'squash_merge_commit_message') of value (...), while only combinations (...) are allowed.`**

: GitHub only accepts some combinations of the title and the message of squash and merge commits, see
  [Control the messages of merge and squash commits](pull-requests.md#control-the-messages-of-merge-and-squash-commits).

## Rulesets and branch protection rules

**`use of organization rulesets requires an 'enterprise' plan, while this organization is currently on a '<plan>' plan.`**

: Otterdog only accepts organization rulesets for organizations on the `enterprise` plan, although GitHub also
  provides them with GitHub Team. Use repository rulesets instead, see
  [Organization-wide rulesets](organization-rulesets.md).

**`<ruleset> has 'enforcement' of value 'evaluate' which is only available for an 'enterprise' plan.`**

: Use `disabled` to prepare a ruleset without enforcing it, see
  [Prepare a ruleset before enforcing it](organization-rulesets.md#prepare-a-ruleset-before-enforcing-it).

**`<ruleset> requires deployment environment '<environment>' which is not defined in the repository itself.`**

: A ruleset or branch protection rule that requires a successful deployment can only reference an environment of
  the same repository. Define the environment in the repository, see
  [Require a successful deployment before merging](environments.md#require-a-successful-deployment-before-merging).

## Plan and apply

**`plan` shows changes that nobody made in the configuration**

: The configuration of the organization only contains the differences to its default configuration. A change of
  the default configuration, or a setting changed in the GitHub web interface, shows up in `plan`, see
  [Inherited and explicit values](inheritance.md).

**A ruleset or branch protection rule created in the GitHub web interface is deleted**

: Otterdog manages all protections of the configured repositories, a protection that is not part of the
  configuration is removed when deletions are applied. Add it to the configuration instead, see the warning in
  [Otterdog specifics](rulesets-vs-branch-protection.md#otterdog-specifics).

**A rotated secret is not updated on GitHub**

: Otterdog cannot detect that the value of a credential changed in the credential provider. Update the secret
  explicitly, see [Updating secret values](secrets-and-variables.md#updating-secret-values).

**Changes to some organization settings are not applied automatically**

: Some settings, e.g. `members_can_create_teams` or the discussions of the organization, can only be changed
  through the GitHub web interface, which requires the credentials of a user that can log in to GitHub. `plan` and
  `apply` skip them with `--no-web-ui`, and such changes merged in a pull request of the configuration repository
  have to be applied manually, see
  [Restrict what members can do](organization-settings.md#restrict-what-members-can-do).
