# Organization Codespaces Secret

Organization Codespaces secrets use the same shape as organization Actions secrets, but are managed through the Codespaces secret API.

```jsonnet
orgs.newOrgCodespacesSecret('CODESPACES_TOKEN') {
  value: 'pass:path/to/codespaces/token',
  visibility: 'selected',
  selected_repositories: ['my-repository'],
}
```

The supported fields are `name`, `value`, `visibility`, and `selected_repositories`. `visibility` can be `public`, `private`, or `selected`. Secret names must be uppercase because GitHub normalizes them to uppercase. Imported values are redacted as `********` and are skipped until a real value is configured.
