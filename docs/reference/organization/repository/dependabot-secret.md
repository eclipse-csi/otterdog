# Repository Dependabot Secret

```jsonnet
orgs.newRepo('my-repository') {
  dependabot_secrets+: [
    orgs.newRepoDependabotSecret('DEPENDABOT_TOKEN') {
      value: 'pass:path/to/dependabot/token',
    },
  ],
}
```

Repository Dependabot secrets support `name` and `value`. Secret names must be uppercase because GitHub normalizes them to uppercase. Imported values are redacted as `********` and are skipped until a real value is configured.
