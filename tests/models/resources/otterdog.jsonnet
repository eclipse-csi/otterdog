// Hint: keep this file identical to otterdog.json for testing Jsonnet parsing.

local VAR = "https://github.com/otterdog/test-defaults#test-defaults.libsonnet@main";

{
  defaults: {
    bitwarden: {
      api_token_key: "api_token_admin",
    },
    jsonnet: {
      # Random Jsonnet feature: using a local variable
      base_template: VAR,
      config_dir: ".",
    },
    github: {
      config_repo: ".eclipsefdn",
    },
  },
  organizations: [
    {
      name: "test-org",
      github_id: "test-org",
    }, // trailing comma allowed in Jsonnet
  ],
}
