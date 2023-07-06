A GitHub Organization 

```json
orgs.newOrg('<github-id>') {
  settings+: {
    blog: "https://adoptium.net",
    default_repository_permission: "none",
    default_workflow_permissions: "write",
    description: "The Adoptium Working Group promotes and supports high-quality runtimes and associated technology for use across the Java ecosystem",
    name: "Eclipse Adoptium",
    readers_can_create_discussions: true,
    security_managers+: [
      "adoptium-project-leads"
    ],
    twitter_username: "adoptium",
    web_commit_signoff_required: false,
  },
  webhooks+: [
    orgs.newOrgWebhook('https://app.codacy.com/2.0/events/gh/organization') {
      content_type: "json",
      events+: [
        "meta",
        "organization",
        "repository"
      ],
      secret: "********",
    },
  ],
  secrets+: [
    orgs.newOrgSecret('ADOPTIUM_AQAVIT_BOT_TOKEN') {
      value: "pass:bots/adoptium.aqavit/github.com/project-token",
    },
    orgs.newOrgSecret('ADOPTIUM_BOT_TOKEN') {
      value: "pass:bots/adoptium/github.com/project-token",
    },
    orgs.newOrgSecret('ADOPTIUM_TEMURIN_BOT_TOKEN') {
      value: "pass:bots/adoptium.temurin/github.com/project-token",
    },
    orgs.newOrgSecret('SLACK_WEBHOOK_CODEFREEZE_URL') {
      value: "pass:bots/adoptium/github.com/slack-webhook-codefreeze-url",
    },
  ],
  _repositories+:: [