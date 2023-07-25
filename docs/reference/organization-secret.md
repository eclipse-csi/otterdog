---
hide:
  - toc
---

### Organizational Secrets

| Field                 | Type           | Description                                                                                 |
|-----------------------|----------------|---------------------------------------------------------------------------------------------|
| name                  | string         | The name of the secret                                                                      |
| visibility            | string         | Controls which repositories can use the secret, can be `public` or `private` or `selected`  |
| selected_repositories | list[string]   | List of repositories that can use the secret, only use if `visibility` is set to `selected` |
| value                 | string         | The secret value                                                                            |

The secret value can be resolved using a credential provider in the same way as for Webhooks.

