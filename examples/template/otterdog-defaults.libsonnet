local otterdog = import 'otterdog-functions.libsonnet';

# Function to create a new repository with default settings.
local newRepo(name) = {
  name: name,
  description: null,
  homepage: null,
  private: false,

  has_discussions: false,
  has_issues: true,
  has_projects: true,
  has_wiki: true,

  topics: [],

  is_template: false,
  template_repository: null,
  auto_init: true,

  forked_repository: null,
  fork_default_branch_only: true,

  default_branch: "main",

  allow_rebase_merge: true,
  allow_merge_commit: false,
  allow_squash_merge: true,

  allow_auto_merge: false,
  delete_branch_on_merge: true,

  allow_update_branch: true,

  # Can be one of: PR_TITLE, COMMIT_OR_PR_TITLE
  squash_merge_commit_title: "COMMIT_OR_PR_TITLE",
  # Can be one of: PR_BODY, COMMIT_MESSAGES, BLANK
  squash_merge_commit_message: "COMMIT_MESSAGES",
  # Can be one of: PR_TITLE, MERGE_MESSAGE
  merge_commit_title: "MERGE_MESSAGE",
  # Can be one of: PR_BODY, PR_TITLE, BLANK
  merge_commit_message: "PR_TITLE",

  archived: false,

  # about private forks
  allow_forking: true,

  web_commit_signoff_required: true,

  # security analysis
  secret_scanning: "enabled",
  secret_scanning_push_protection: "enabled",

  dependabot_alerts_enabled: true,
  dependabot_security_updates_enabled: false,

  # disable reporting by default for now
  private_vulnerability_reporting_enabled: false,

  # code scanning default setup
  code_scanning_default_setup_enabled: false,
  code_scanning_default_query_suite: "default",
  code_scanning_default_languages: [],

  # GitHub pages
  gh_pages_build_type: "disabled",
  gh_pages_source_branch: null,
  gh_pages_source_path: null,

  # Custom Properties
  custom_properties: {},

  workflows: {
    enabled: true,

    # allow all actions by default
    allowed_actions: "all",
    allow_github_owned_actions: true,
    allow_verified_creator_actions: true,
    allow_action_patterns: [],

    # issue read tokens by default
    default_workflow_permissions: "read",

    # allow actions to approve and merge pull requests
    actions_can_approve_pull_request_reviews: true,
  },

  # repository webhooks
  webhooks: [],

  # repository secrets
  secrets: [],

  # repository variables
  variables: [],

  # repository environments
  environments: [],

  # branch protection rules
  branch_protection_rules: [],

  # rulesets
  rulesets: []
};

# Function to extend an existing repo with the same name.
local extendRepo(name) = {
   name: name
};

# Function to create a new branch protection rule with default settings.
local newBranchProtectionRule(pattern) = {
  pattern: pattern,
  allows_deletions: false,
  allows_force_pushes: false,
  bypass_force_push_allowances: [],
  bypass_pull_request_allowances: [],
  dismisses_stale_reviews: false,
  is_admin_enforced: false,
  lock_allows_fetch_and_merge: false,
  lock_branch: false,
  restricts_pushes: false,
  blocks_creations: false,
  push_restrictions: [],
  required_status_checks: [],
  requires_pull_request: true,
  required_approving_review_count: 2,
  requires_code_owner_reviews: false,
  requires_commit_signatures: false,
  requires_conversation_resolution: false,
  requires_linear_history: false,
  requires_status_checks: true,
  requires_strict_status_checks: false,
  restricts_review_dismissals: false,
  review_dismissal_allowances: [],
  require_last_push_approval: false,
  requires_deployments: false,
  required_deployment_environments: []
};

# Function to create a pull request with default settings.
local newPullRequest() = {
  required_approving_review_count: 2,
  requires_code_owner_review: false,
  requires_last_push_approval: false,
  requires_review_thread_resolution: false,
  dismisses_stale_reviews: false,
};

# Function to create status checks with default settings.
local newStatusChecks() = {
  do_not_enforce_on_create: false,
  strict: false,
  status_checks: [],
};

# Function to create a new repository ruleset with default settings.
local newRepoRuleset(name) = {
  name: name,
  enforcement: "active",
  target: "branch",

  include_refs: [],
  exclude_refs: [],

  allows_creations: false,
  allows_deletions: false,
  allows_force_pushes: false,
  allows_updates: true,

  bypass_actors: [],

  required_pull_request: newPullRequest(),
  required_status_checks: newStatusChecks(),

  requires_linear_history: false,
  requires_commit_signatures: false,

  requires_deployments: false,
  required_deployment_environments: [],

  required_merge_queue: null,
};

# Function to create a merge queue with default settings.
local newMergeQueue() = {
  merge_method: "MERGE",
  build_concurrency: 5,
  min_group_size: 1,
  max_group_size: 5,
  wait_time_for_minimum_group_size: 5,
  status_check_timeout: 60,
  requires_all_group_entries_to_pass_required_checks: true,
};

# Function to create a new organization ruleset with default settings.
local newOrgRuleset(name) = newRepoRuleset(name) {
  include_repo_names: [],
  exclude_repo_names: [],
  protect_repo_names: false,
};

# Function to create a new organization webhook with default settings.
local newOrgWebhook(url) = {
  active: true,
  events: [],
  url: url,
  # Can be one of: form, json
  content_type: "form",
  insecure_ssl: "0",
  secret: null,
};

# Function to create a new repository webhook with default settings.
local newRepoWebhook(url) = newOrgWebhook(url);

# Function to create a new repository secret with default settings.
local newRepoSecret(name) = {
  name: name,
  value: null
};

# Function to create a new organization secret with default settings.
local newOrgSecret(name) = newRepoSecret(name) {
  visibility: "public",
  selected_repositories: [],
};

# Function to create a new repository variable with default settings.
local newRepoVariable(name) = {
  name: name,
  value: null
};

# Function to create a new organization variable with default settings.
local newOrgVariable(name) = newRepoVariable(name) {
  visibility: "public",
  selected_repositories: [],
};

# Function to create a new organization role with default settings.
local newOrgRole(name) = {
  name: name,
  description: "",
  permissions: [],
  base_role: "none",
};

# Function to create a new team with default settings.
local newTeam(name) = {
  name: name,
  description: "",
  privacy: "visible",
  notifications: true,
  members: [],
  skip_members: false,
  skip_non_organization_members: false,
};

# Function to create a new environment with default settings.
local newEnvironment(name) = {
  name: name,
  wait_timer: 0,
  reviewers: [],
  # Can be one of: all, protected_branches, branch_policies
  deployment_branch_policy: "all",
  branch_policies: [],
};

# Function to create a new custom property with default settings.
local newCustomProperty(name) = {
  name: name,
  value_type: "string",
  required: false,
  default_value: null,
  description: null,
  allowed_values: [],
};

# Function to create a new organization with default settings.
local newOrg(name, id=name) = {
  project_name: name,
  github_id: id,
  settings: {
    name: null,
    plan: "free",
    billing_email: "",
    company: null,
    email: null,
    twitter_username: null,
    location: null,
    description: null,
    blog: null,

    has_discussions: false,
    discussion_source_repository: null,

    has_organization_projects: true,

    # Base permissions to the organization’s repositories apply to all members and exclude outside collaborators.
    # Since organization members can have permissions from multiple sources, members and collaborators who have been
    # granted a higher level of access than the base permissions will retain their higher permission privileges.
    # Can be one of: read, write, admin, none
    default_repository_permission: "read",

    # Repository creation
    members_can_create_private_repositories: false,
    members_can_create_public_repositories: false,

    # Repository forking
    members_can_fork_private_repositories: false,

    # Repository defaults: Commit signoff
    web_commit_signoff_required: true,

    # GitHub Pages
    members_can_create_public_pages: true,

    # Disable default code security configurations
    default_code_security_configurations_disabled: true,

    ## Admin repository permissions

    # If enabled, members with admin permissions for the repository will be able to change its visibility.
    # If disabled, only organization owners can change repository visibilities.
    members_can_change_repo_visibility: false,

    # If enabled, members with admin permissions for the repository will be able to delete or transfer public
    # and private repositories. If disabled, only organization owners can delete or transfer repositories.
    members_can_delete_repositories: false,

    # If enabled, members with admin permissions for the repository will be able to delete issues.
    # If disabled, only organization owners can delete issues.
    members_can_delete_issues: false,

    # If enabled, all users with read access can create and comment on discussions in repositories of the organization.
    # If disabled, discussion creation is limited to users with at least triage permission.
    # Users with read access can still comment on discussions.
    readers_can_create_discussions: true,

    ## Member team permissions

    # If enabled, any member of the organization will be able to create new teams.
    # If disabled, only organization owners can create new teams.
    members_can_create_teams: false,

    two_factor_requirement: true,

    default_branch_name: "main",

    packages_containers_public: true,
    packages_containers_internal: true,

    members_can_change_project_visibility: true,

    security_managers: [],

    custom_properties: [],

    workflows: {
      # enable workflows for all repositories
      enabled_repositories: "all",
      selected_repositories: [],

      # allow all actions by default
      allowed_actions: "all",
      allow_github_owned_actions: true,
      allow_verified_creator_actions: true,
      allow_action_patterns: [],

      # issue read tokens by default
      default_workflow_permissions: "read",

      # allow actions to approve and merge pull requests
      actions_can_approve_pull_request_reviews: true,
    }
  },

  # organization roles
  roles: [],

  # organization teams
  teams: [],

  # organization secrets
  secrets: [],

  # organization variables
  variables: [],

  # organization webhooks
  webhooks: [],

  # organization rulesets
  rulesets: [],

  # List of repositories of the organization.
  # Entries here can be extended during template manifestation:
  #  * new repos should be defined using the newRepo template
  #  * extending existing repos inherited from the default config should be defined using the extendRepo template
  _repositories:: [],

  # Merges configuration settings for repositories defined in _repositories
  # using the name of the repo as key. The result is a unique array of repository
  # configurations.
  repositories: otterdog.mergeByKey(self._repositories, "name"),
};

{
  newOrg:: newOrg,
  newOrgRole:: newOrgRole,
  newTeam:: newTeam,
  newOrgWebhook:: newOrgWebhook,
  newOrgSecret:: newOrgSecret,
  newOrgVariable:: newOrgVariable,
  newOrgRuleset:: newOrgRuleset,
  newCustomProperty:: newCustomProperty,
  newRepo:: newRepo,
  extendRepo:: extendRepo,
  newRepoWebhook:: newRepoWebhook,
  newRepoSecret:: newRepoSecret,
  newRepoVariable:: newRepoVariable,
  newBranchProtectionRule:: newBranchProtectionRule,
  newRepoRuleset:: newRepoRuleset,
  newEnvironment:: newEnvironment,
  newPullRequest:: newPullRequest,
  newStatusChecks:: newStatusChecks,
  newMergeQueue:: newMergeQueue,
}
