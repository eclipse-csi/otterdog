// Hint: keep this file identical to otterdog.json for testing Jsonnet parsing.

local VAR = "https://github.com/otterdog/test-defaults#test-defaults.libsonnet@main";

{
  defaults: {
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
      credentials: {
        provider: "plain",
        api_token: "test-token",
        username: "test-user",
        password: "test-pass",
        twofa_seed: ""
      }
    }, // trailing comma allowed in Jsonnet
  ],
}
