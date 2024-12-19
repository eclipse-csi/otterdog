
local orgs = import 'vendor/test-defaults/test-defaults.libsonnet';

orgs.newOrg('test-org', 'test-org') {
    settings+: {
      billing_email: "info@test.org",
      blog: "https://www.test.org",
      description: "",
      email: "info@test.org",
      name: "test.org",
      packages_containers_internal: false,
      packages_containers_public: false,
      readers_can_create_discussions: true,
    },
    webhooks+: [
      orgs.newOrgWebhook('https://www.example.org')
    ],
    repositories+: [
      orgs.newRepo('test-repo') {
        allow_auto_merge: false,
        allow_merge_commit: true,
        allow_rebase_merge: false,
        allow_squash_merge: true,
        allow_update_branch: false,
        delete_branch_on_merge: false,
        merge_commit_title: "MERGE_MESSAGE",
        squash_merge_commit_message: "COMMIT_MESSAGES",
        squash_merge_commit_title: "COMMIT_OR_PR_TITLE",
      }
    ]
}
