# Repository Codespaces Secret

```jsonnet
orgs.newRepo('my-repository') {
  codespaces_secrets+: [
    orgs.newRepoCodespacesSecret('CODESPACES_TOKEN') {
      value: 'pass:path/to/codespaces/token',
    },
  ],
}
```

Repository Codespaces secrets support `name` and `value`. Secret names must be uppercase because GitHub normalizes them to uppercase. Imported values are redacted as `********` and are skipped until a real value is configured.
