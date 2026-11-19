# Workflow for changes

Every change to a GitHub organization managed by otterdog is a pull request on its configuration repository. The
otterdog GitHub App checks the pull request, tells you whether you can merge it yourself, and applies the changes to
GitHub once it is merged.

<!-- the Playground, the easiest way to prepare a change, drawn by docs/assets/theme.css -->
<div class="otterdog-hero" markdown>

:material-code-braces:{ .otterdog-hero__icon }

<div class="otterdog-hero__body" markdown>

**Start in the Playground, nothing to install**

The Playground of the otterdog dashboard edits the configuration of your organization in your browser. It completes
and documents the configuration as you type, shows what your change modifies, validates it with otterdog and turns it
into a pull request.

[:material-open-in-new: Open the dashboard](https://otterdog.eclipse.org){ .md-button .md-button--primary }
[What it does](#what-the-playground-does-for-you){ .md-button }

</div>

</div>

## TL;DR

<!-- the steps of a change, drawn by docs/assets/theme.css -->
<div class="otterdog-flow" markdown>

<div class="otterdog-flow__step" markdown>

:material-code-braces:{ .otterdog-flow__icon }

**Prepare**

Edit the configuration in the Playground of the dashboard, or on a branch with git.

</div>

<div class="otterdog-flow__step" markdown>

:material-source-pull:{ .otterdog-flow__icon }

**Propose**

Propose on GitHub from the Playground, or open a pull request from your branch.

</div>

<div class="otterdog-flow__step" markdown>

:material-shield-check-outline:{ .otterdog-flow__icon }

**Check**

otterdog validates the change and shows its diff, the approval teams review it.

</div>

<div class="otterdog-flow__step" markdown>

:material-rocket-launch-outline:{ .otterdog-flow__icon }

**Merge & apply**

You merge it with `/otterdog merge`, or an admin does, then otterdog applies it.

</div>

</div>

!!! success "Merge it yourself with `/otterdog merge` when your pull request"

    - is **ready for review** and passed the **validation** of otterdog for its latest commit,
    - adds or changes **no secret**, **no webhook with a secret** and **no setting of the Web UI**, incurs
      **no cost**, **removes nothing** and only modifies `otterdog/<org>.jsonnet`,
    - is **written or approved by a member of an approval team**, e.g. the project leads, or of an admin team.

    The details: [Can my pull request be auto-merged?](#can-my-pull-request-be-auto-merged)

<!-- the two ways to merge, drawn by docs/assets/theme.css -->
<div class="otterdog-outcomes" markdown>

<div class="otterdog-outcome otterdog-outcome--ok" markdown>

:material-rocket-launch-outline: You merge it

All the conditions are met: comment `/otterdog merge`, otterdog merges the pull request and applies it.

</div>

<div class="otterdog-outcome otterdog-outcome--admin" markdown>

:material-account-group-outline: An admin merges it

Otherwise, a member of the admin teams reviews and merges the pull request, then otterdog applies it.

</div>

</div>

??? info "Approval teams and admin teams"

    Two groups of teams of the organization play a role in this workflow:

    - the **approval teams**: their members can approve a pull request so that it can be auto-merged, and auto-merge
      their own pull requests. By default, these are the teams whose name ends with `project-leads`.
    - the **admin teams**, by default `otterdog-admins`. They can do everything the approval teams can, merge the
      pull requests that cannot be auto-merged and finish applying the changes otterdog cannot apply alone.

    The teams are configured by the operators of otterdog, the help comment that otterdog adds to every pull request
    names them for your organization.

The rest of this page details each step.

## 1. Prepare your change

The **Playground** of the dashboard is the easiest way to prepare a change: everything happens in your browser, it
checks your change as you type and opens the pull request for you. You can also prepare the change locally with git,
both end with a pull request on the configuration repository.

<!-- the two ways to prepare a change, drawn by docs/assets/theme.css -->
<div class="otterdog-lane otterdog-lane--featured" markdown>

<div class="otterdog-lane__title" markdown>:material-star-outline: Recommended · in the browser, with the Playground</div>

<div class="otterdog-flow" markdown>

<div class="otterdog-flow__step" markdown>

:material-view-dashboard-outline:{ .otterdog-flow__icon }

**Dashboard**

Open your organization in the [dashboard](https://otterdog.eclipse.org), or one of its repositories.

</div>

<div class="otterdog-flow__step" markdown>

:material-code-braces:{ .otterdog-flow__icon }

**Playground**

Edit the configuration, check it with Validate.

</div>

<div class="otterdog-flow__step" markdown>

:material-content-copy:{ .otterdog-flow__icon }

**Propose on GitHub**

Copies the configuration, opens the editor of GitHub.

</div>

<div class="otterdog-flow__step" markdown>

:material-source-pull:{ .otterdog-flow__icon .otterdog-flow__icon--done }

**Pull request**

Paste, commit on a new branch, create the pull request.

</div>

</div>

</div>

<div class="otterdog-lane" markdown>

<div class="otterdog-lane__title" markdown>:material-git: Locally with git</div>

<div class="otterdog-flow" markdown>

<div class="otterdog-flow__step" markdown>

:material-source-fork:{ .otterdog-flow__icon }

**Fork & clone**

Fork the configuration repository if you cannot push to it.

</div>

<div class="otterdog-flow__step" markdown>

:material-source-branch:{ .otterdog-flow__icon }

**Branch**

Create a branch from `main`.

</div>

<div class="otterdog-flow__step" markdown>

:material-file-code-outline:{ .otterdog-flow__icon }

**Edit & commit**

Edit the configuration, commit with a clear message.

</div>

<div class="otterdog-flow__step" markdown>

:material-source-pull:{ .otterdog-flow__icon .otterdog-flow__icon--done }

**Pull request**

Push your branch, open the pull request against `main`.

</div>

</div>

</div>

### What the Playground does for you

<div class="grid cards" markdown>

-   :material-auto-fix:{ .lg .middle } **Completes and documents**

    ---

    Typing `orgs.` offers the functions of the configuration, and inside a resource its properties with their default
    value. Hovering a name shows its documentation, with a link to the Reference.

-   :material-spellcheck:{ .lg .middle } **Checks as you type**

    ---

    The configuration is evaluated while you edit it: the errors of Jsonnet, the invalid values and the unknown
    properties are underlined.

-   :material-file-compare:{ .lg .middle } **Shows your changes**

    ---

    The **Changes** tab lists what your change modifies, compared to the current configuration of your organization.

-   :material-shield-check-outline:{ .lg .middle } **Validates with otterdog**

    ---

    **Validate** has the configuration validated by otterdog on the server, like a pull request, except for the
    checks that need the live settings of GitHub, see
    [Validation in the Playground](guides/troubleshooting.md#validation-in-the-playground).

-   :material-book-open-variant:{ .lg .middle } **Starts from examples**

    ---

    The examples of the [configuration guides](guides/index.md) are listed next to the editor: open one to start from
    it.

-   :material-source-pull:{ .lg .middle } **Shares and proposes**

    ---

    **Copy link** shares your changes, e.g. to discuss them, and **Propose on GitHub** turns them into a pull request.

</div>

### Step by step

=== ":material-code-braces: From the Playground"

    The Playground of the [dashboard](https://otterdog.eclipse.org) opens the current configuration of your
    organization in an editor that evaluates it as you type and documents its properties.

    1. **Open the Playground of your organization**: on the page of your organization in the dashboard, click on
       **Playground**. On the page of a repository, **Edit in Playground** opens the configuration at this repository.
    2. **Edit the configuration**, see the [configuration guides](guides/index.md) and the
       [Reference](../reference/index.md).
    3. **Validate** checks the configuration with otterdog on the server, like the validation of a pull request,
       except for the checks that need the live settings of GitHub.
    4. **Propose on GitHub** copies the configuration and opens the editor of GitHub on `otterdog/<org>.jsonnet`.
    5. **Paste** the copied configuration over the content of the file: ++ctrl+a++ then ++ctrl+v++ (++cmd++ instead
       of ++ctrl++ on macOS).
    6. **Commit changes…**: choose to create a new branch, with a clear and descriptive message, then click on
       **Propose changes** and **Create pull request**. GitHub creates the pull request from your account, and forks
       the repository first if you cannot push to it.

    **Copy link** gives a link opening the Playground with your changes, e.g. to discuss them before proposing them.

=== ":material-git: Locally with git"

    1. **Find the configuration repository** of your GitHub organization, e.g. `.eclipsefdn`.
    2. **Fork it if needed**: without write access, fork it according to your corporate guidelines or to your
       personal GitHub account. If forking is not allowed, contact the maintainers of the organization.
    3. **Clone it and create a branch** from `main`, e.g. `git switch -c my-change`.
    4. **Edit the configuration**: the entry point is `otterdog/<org>.jsonnet`. See the
       [configuration guides](guides/index.md) and the [Reference](../reference/index.md). The
       [Playground](https://otterdog.eclipse.org/playground) can try out a snippet before you write it in the file.
    5. **Commit** with a clear and descriptive message, then push your branch.

!!! tip "Start from the latest configuration"

    - **Playground**: the content you paste replaces the whole file, so it reverts the changes merged since you
      opened the Playground, e.g. a repository added in the meantime shows up as removed, which also prevents the
      auto-merge. Reload the Playground before editing if the configuration may have changed since you opened it.
    - **git**: your branch does not need to be up to date, otterdog validates the merge of your latest commit into
      `main` that GitHub prepares when you push, and the validation comment tells which commit of `main` it merges
      into. If GitHub cannot merge it, e.g. because of a conflict, otterdog compares your branch with the **latest**
      commit of `main` instead: the changes merged since you started then appear as reverted, and the validation
      comment asks you to update the branch. Rebase your branch on `main`, or merge `main` into it, and push again.

## 2. Open a pull request

From the Playground, the editor of GitHub opens the pull request with **Create pull request**. With git, push your
branch and open a pull request against the `main` branch of the configuration repository. Only a pull request ready
for review is checked: a draft is checked once you mark it as **Ready for review**.

otterdog then follows the pull request with comments and status checks, like this in its conversation on GitHub:

<!-- the legend of the timeline below, drawn by docs/assets/theme.css -->
<div class="otterdog-legend" markdown>

:material-robot-outline:{ .otterdog-timeline__icon } **otterdog**, automatically

:material-account-outline:{ .otterdog-timeline__icon .otterdog-timeline__icon--person } **You** or a reviewer

</div>

<!-- the events of a pull request, drawn by docs/assets/theme.css -->
<div class="otterdog-timeline" markdown>

<div class="otterdog-timeline__phase" markdown>Opened or marked ready for review</div>

<div class="otterdog-timeline__event" markdown>

:material-source-pull:{ .otterdog-timeline__icon .otterdog-timeline__icon--person }

**You** open the pull request, or mark your draft as ready for review.

</div>

<div class="otterdog-timeline__event" markdown>

:material-comment-processing-outline:{ .otterdog-timeline__icon }

**Help** comment: the conditions of the auto-merge, the commands, and the approval and admin teams of your
organization.

</div>

<div class="otterdog-timeline__event" markdown>

:material-account-group-outline:{ .otterdog-timeline__icon }

**Team info** comment: your role in the organization and your teams, which decide whether you need an approval.

</div>

<div class="otterdog-timeline__phase" markdown>When opened and on every push</div>

<div class="otterdog-timeline__event" markdown>

:material-shield-check-outline:{ .otterdog-timeline__icon }

**Validation**: the status check `otterdog-validate`, and a comment with the diff otterdog would apply, its warnings
and, if so, why the pull request cannot be auto-merged.

</div>

<div class="otterdog-timeline__event" markdown>

:material-sync:{ .otterdog-timeline__icon }

**Sync check**: the status check `otterdog-sync`, always successful, and a comment only if `main` differs from the
live settings, for information.

</div>

<div class="otterdog-timeline__phase" markdown>Review and merge</div>

<div class="otterdog-timeline__event" markdown>

:material-account-check-outline:{ .otterdog-timeline__icon .otterdog-timeline__icon--person }

**A reviewer** of an approval team approves the pull request, unless you are a member of one.

</div>

<div class="otterdog-timeline__event" markdown>

:material-check-decagram-outline:{ .otterdog-timeline__icon }

**Ready to merge** at the top of the validation comment, once all the conditions are met: you can merge the pull
request yourself. The validation comment is updated in place: it shows it as soon as they are met, e.g. after an
approval, and no longer once they are not, e.g. on a push, a dismissed approval or a conversion to a draft.

</div>

<div class="otterdog-timeline__event" markdown>

:material-console-line:{ .otterdog-timeline__icon .otterdog-timeline__icon--person }

**You** comment `/otterdog merge`, otterdog squash-merges the pull request.

</div>

<div class="otterdog-timeline__event" markdown>

:material-rocket-launch-outline:{ .otterdog-timeline__icon }

**Applied** comment: otterdog applied the changes to the organization, see [5. Apply](#5-apply).

</div>

</div>

A new comment of the same kind hides the previous one as outdated, the last one is always the current one. Bots do
not get the help and team-info comments.

### What otterdog compares

<!-- the comparisons of otterdog, drawn by docs/assets/theme.css -->
<div class="otterdog-outcomes" markdown>

<div class="otterdog-outcome" markdown>

:material-shield-check-outline: Validate

`main` :material-arrow-left-right: your branch

The diff of the validation comment: what merging the pull request changes, even if your branch is behind `main`.

</div>

<div class="otterdog-outcome otterdog-outcome--info" markdown>

:material-sync: Check sync

`main` :material-arrow-left-right: GitHub

The settings changed on GitHub outside the configuration, for information: it never blocks the merge.

</div>

<div class="otterdog-outcome otterdog-outcome--ok" markdown>

:material-rocket-launch-outline: Apply

pull request :material-arrow-right: GitHub

After the merge, only the changes of the pull request: the other differences are left untouched.

</div>

</div>

The validation diff shows `+` create, `~` modify, `!` forced update and `-` delete. If the configuration contains
errors, the `otterdog-validate` status fails: fix the configuration and push again.

## 3. Review

Request the reviews needed for your change, mandatory reviewers are assigned automatically. Address the review
comments by pushing to your branch, otterdog checks every new commit again.

An approval counts for the auto-merge when its author is a member of an **approval team** or of an **admin team**.

## 4. Merge

<!-- the two ways to merge, drawn by docs/assets/theme.css -->
<div class="otterdog-outcomes" markdown>

<div class="otterdog-outcome otterdog-outcome--ok" markdown>

:material-rocket-launch-outline: Auto-merge with `/otterdog merge`

When the pull request meets all the conditions below, the validation comment shows **Ready to merge**. Comment
`/otterdog merge`: otterdog squash-merges the pull request, then applies it. If a condition is not met, otterdog
replies with what is missing and how to proceed.

</div>

<div class="otterdog-outcome otterdog-outcome--admin" markdown>

:material-account-group-outline: Merge by an admin

A pull request that cannot be auto-merged is reviewed and merged by a member of the admin teams. The validation
comment explains why, and notifies the admin teams.

</div>

</div>

### Can my pull request be auto-merged?

`/otterdog merge` checks four conditions, all of them are required:

<!-- the conditions of the auto-merge, drawn by docs/assets/theme.css -->
<div class="otterdog-timeline" markdown>

<div class="otterdog-timeline__event" markdown>

:material-console-line:{ .otterdog-timeline__icon .otterdog-timeline__icon--person }

**You comment `/otterdog merge`** on the pull request.

</div>

<div class="otterdog-timeline__event" markdown>

:material-shield-check-outline:{ .otterdog-timeline__icon }

**1. Open, ready for review, and its latest commit validated without errors?**
<span class="otterdog-timeline__else">Otherwise: fix the configuration and push, mark the draft as ready for review, or wait for the validation of your latest commit.</span>

</div>

<div class="otterdog-timeline__event" markdown>

:material-file-check-outline:{ .otterdog-timeline__icon }

**2. Only changes otterdog can apply alone?** No secret, no setting of the Web UI, no cost, no removal and no other
file than the configuration, see [below](#changes-that-prevent-the-auto-merge).
<span class="otterdog-timeline__else">Otherwise: an admin reviews and merges the pull request.</span>

</div>

<div class="otterdog-timeline__event" markdown>

:material-account-check-outline:{ .otterdog-timeline__icon }

**3. Written or approved by a member of an approval or admin team?**
<span class="otterdog-timeline__else">Otherwise: ask a member of an approval team for a review.</span>

</div>

<div class="otterdog-timeline__event" markdown>

:material-account-group-outline:{ .otterdog-timeline__icon }

**4. Commented by the author, or by a member of an approval or admin team?**
<span class="otterdog-timeline__else">Otherwise: the command is refused.</span>

</div>

<div class="otterdog-timeline__event" markdown>

:material-rocket-launch-outline:{ .otterdog-timeline__icon .otterdog-timeline__icon--done }

**Squash merge, then apply**: otterdog merges the pull request and applies its changes.

</div>

</div>

!!! tip "`/otterdog merge` refused?"

    otterdog replies with the conditions that are not met. What to do for each of its messages:
    [Merging with `/otterdog merge`](guides/troubleshooting.md#merging-with-otterdog-merge).

### Changes that prevent the auto-merge

These changes always need a member of the admin teams, whoever the author is:

<div class="grid cards" markdown>

-   :material-key-variant:{ .lg .middle } **Secrets**

    ---

    Adds or changes a [secret](guides/secrets-and-variables.md) of the organization, a repository or an environment,
    or a [webhook](guides/webhooks.md) with a secret. otterdog does not apply secret values from a pull request, an
    admin applies them.

-   :material-web:{ .lg .middle } **Settings of the Web UI**

    ---

    Changes an [organization setting](../reference/organization/settings.md) only available in the web interface of
    GitHub, e.g. `members_can_create_teams`, `default_branch_name` or `has_discussions`. An admin applies it.

-   :material-currency-usd:{ .lg .middle } **Costs**

    ---

    Creates a private repository or makes one private, changes the GitHub Actions cache size limit
    `max_cache_size_gb`, or
    enables licensed code security products for private repositories, see the
    [cost policy](../operating_otterdog/setup.md#cost-policy).

-   :material-delete-outline:{ .lg .middle } **Removals**

    ---

    [Removes a resource](resources.md#removing-a-resource): a repository, a team, a webhook, a ruleset, a secret, a variable, an
    environment... Removals you did not make come from a configuration older than `main`, see
    [Start from the latest configuration](#1-prepare-your-change).

-   :material-file-document-multiple-outline:{ .lg .middle } **Other files**

    ---

    Modifies another file than `otterdog/<org>.jsonnet`, e.g. the README of the configuration repository or a
    workflow.

-   :material-check-decagram-outline:{ .lg .middle } **Everything else can be auto-merged**

    ---

    E.g. the settings and features of public repositories, branch protection rules and rulesets, teams, variables
    and environments.

</div>

!!! tip "Split your pull request"

    If only a part of your change prevents the auto-merge, move it to a pull request of its own: the rest can be
    auto-merged right away.

### Who can do what

|                                                        | Any contributor  | Member of an approval team | Member of an admin team |
|--------------------------------------------------------|:----------------:|:--------------------------:|:-----------------------:|
| Open a pull request                                    | :material-check: | :material-check:           | :material-check:        |
| Approve, with the approval counting for the auto-merge |                  | :material-check:           | :material-check:        |
| Auto-merge their own pull request without approval     |                  | :material-check:           | :material-check:        |
| `/otterdog merge` their own approved pull request      | :material-check: | :material-check:           | :material-check:        |
| `/otterdog merge` the eligible pull request of others  |                  | :material-check:           | :material-check:        |
| Merge a pull request that cannot be auto-merged        |                  |                            | :material-check:        |
| `/otterdog apply`, `/otterdog done`                    |                  |                            | :material-check:        |

To be considered a member of a team, the author must be a member of the organization: an outside collaborator always
needs an approval.

## 5. Apply

Once the pull request is merged into `main`, otterdog applies its changes to the GitHub organization and comments the
result on the pull request.

<!-- the results of the apply, drawn by docs/assets/theme.css -->
<div class="otterdog-outcomes" markdown>

<div class="otterdog-outcome otterdog-outcome--ok" markdown>

:material-check-circle-outline: Applied

All the changes are live on GitHub, there is nothing left to do.

</div>

<div class="otterdog-outcome otterdog-outcome--warn" markdown>

:material-progress-wrench: Partially applied

The pull request contains secrets or settings of the Web UI, which otterdog does not apply on its own. The admin
teams are notified, apply the rest, then comment `/otterdog done`.

</div>

<div class="otterdog-outcome otterdog-outcome--ko" markdown>

:material-close-circle-outline: Failed

The comment shows the error and notifies the admin teams. Once the cause is fixed, they apply the pull request again
with `/otterdog apply`.

</div>

</div>

!!! warning "Do not merge a pull request whose validation failed"

    otterdog only applies a pull request whose last validation succeeded. If such a pull request is merged anyway,
    its changes are not applied: contact the admin teams.

## Commands

Comment on the pull request to run otterdog. The commands are grouped by when you use them, and by who can use
them:

<!-- the commands, grouped by when and by whom they are used, drawn by docs/assets/theme.css -->
<div class="otterdog-lane otterdog-commands" markdown>

<div class="otterdog-lane__title" markdown>
:material-source-pull: While the pull request is open · anyone
</div>

`/otterdog validate`
:   Validates the pull request again and updates the `otterdog-validate` check, e.g. to validate a draft, which is
    not validated automatically.

`/otterdog validate info`
:   The same, and the validation comment also lists the information messages.

`/otterdog check-sync`
:   Compares `main` with the live settings of the organization again and updates the `otterdog-sync` check. A
    comment shows the differences, if any: they never prevent the merge.

`/otterdog team-info`
:   Retrieves the teams of the author again, e.g. after they joined an approval team, and lists them in a comment.

`/otterdog help`
:   Adds the help comment again.

</div>

<div class="otterdog-lane otterdog-lane--ok otterdog-commands" markdown>

<div class="otterdog-lane__title" markdown>
:material-rocket-launch-outline: To merge · the author, approval and admin teams
</div>

`/otterdog merge`
:   Checks the [conditions of the auto-merge](#can-my-pull-request-be-auto-merged), then squash-merges the pull
    request and applies it. Otherwise, replies with what is missing, see
    [Troubleshooting](guides/troubleshooting.md#merging-with-otterdog-merge).

</div>

<div class="otterdog-lane otterdog-lane--admin otterdog-commands" markdown>

<div class="otterdog-lane__title" markdown>
:material-account-group-outline: After the merge · the admin teams
</div>

`/otterdog apply`
:   Applies the merged pull request again, e.g. after a failure. Ignored if the pull request is already applied, or
    if its last validation failed.

`/otterdog done`
:   Marks the merged pull request as applied, once the admin applied the rest by hand, e.g. the secrets. It applies
    nothing itself.

</div>

!!! note "How otterdog reads a comment"

    - The comment must **start** with the command, the rest is ignored: `/otterdog merge, thanks!` merges, but
      `Thanks! /otterdog merge` does nothing. A comment runs one command only.
    - Editing a comment runs its command again.
    - When you are not allowed to use `/otterdog merge`, `/otterdog apply` or `/otterdog done`, otterdog replies with
      a warning naming the teams that are.
