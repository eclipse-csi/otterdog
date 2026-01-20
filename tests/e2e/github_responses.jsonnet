local org_response = import '../models/resources/github-org-settings.json';
local repo_response = import '../models/resources/github-repo.json';

{
  // Reuse some data from resources directory
  '/repos/test-org/otterdog-defaults': repo_response,
  '/repos/test-org/.eclipsefdn': repo_response,
  '/orgs/test-org': org_response,
  '/orgs/test-org/repos': [repo_response],

  // Repository endpoints for otterdog-defaults
  '/repos/test-org/otterdog-defaults/private-vulnerability-reporting': { enabled: false },
  '/repos/test-org/otterdog-defaults/vulnerability-alerts': { enabled: false },
  '/repos/test-org/otterdog-defaults/pages': { url: 'https://test-org.github.io/otterdog-defaults' },
  '/repos/test-org/otterdog-defaults/hooks': [],
  '/repos/test-org/otterdog-defaults/topics': { names: [] },
  '/repos/test-org/otterdog-defaults/rulesets': [],
  '/repos/test-org/otterdog-defaults/code-scanning/default-setup': { state: 'configured' },
  '/repos/test-org/otterdog-defaults/dependency-graph/sbom': { sbom: { name: 'test-repo' } },
  '/repos/test-org/otterdog-defaults/properties/values': [],
  '/repos/test-org/otterdog-defaults/actions/permissions': { enabled: true },
  '/repos/test-org/otterdog-defaults/actions/permissions/selected-actions': {},
  '/repos/test-org/otterdog-defaults/actions/permissions/workflow': {},
  '/repos/test-org/otterdog-defaults/actions/secrets': { secrets: [] },
  '/repos/test-org/otterdog-defaults/actions/variables': { variables: [] },
  '/repos/test-org/otterdog-defaults/actions/secrets/public-key': { key: 'abcd123456', key_id: '123456' },
  '/repos/test-org/otterdog-defaults/environments': { environments: [] },
  '/repos/test-org/otterdog-defaults/properties': { properties: [] },

  // Additional endpoints for apply operations
  '/repos/EclipseFdn/.eclipsefdn-template/generate': {
    repository: { name: '.eclipsefdn', full_name: 'test-org/.eclipsefdn' },
  },
  '/repos/test-org/.eclipsefdn/vulnerability-alerts': { enabled: false },
  '/repos/test-org/.eclipsefdn/private-vulnerability-reporting': { enabled: false },
  '/repos/test-org/.eclipsefdn/pages': { url: 'https://test-org.github.io/.eclipsefdn' },
  '/repos/test-org/.eclipsefdn/topics': { names: [] },
  '/repos/test-org/.eclipsefdn/hooks': [],
  '/repos/test-org/.eclipsefdn/code-scanning/default-setup': { state: 'configured' },
  '/repos/test-org/.eclipsefdn/properties/values': [],
  '/repos/test-org/.eclipsefdn/actions/permissions': { enabled: true },
  '/repos/test-org/.eclipsefdn/actions/permissions/selected-actions': {},
  '/repos/test-org/.eclipsefdn/actions/permissions/workflow': {},
  '/repos/test-org/.eclipsefdn/actions/secrets': { secrets: [] },
  '/repos/test-org/.eclipsefdn/actions/variables': { variables: [] },
  '/repos/test-org/.eclipsefdn/environments': { environments: [] },
  '/repos/test-org/.eclipsefdn/readme': {
    name: 'README.md',
    path: 'README.md',
    content: 'VGVzdCBSZWFkbWU=',  // Base64 encoded "Test Readme"
    type: 'file',
  },

  // Organization endpoints
  '/orgs/test-org/properties/schema': [
    {
      property_name: 'test',
      url: 'https://github.com',
      description: 'test property',
      value_type: 'string',
    },
  ],
  '/orgs/test-org/properties/values': [],
  '/orgs/test-org/installations': { installations: [] },
  '/orgs/test-org/organization-roles': { roles: [] },
  '/orgs/test-org/settings/billing/actions': { total_minutes_used: 0, included_minutes: 0 },
  '/orgs/test-org/teams': [],
  '/orgs/test-org/hooks': [],
  '/orgs/test-org/members': [],
  '/orgs/test-org/outside_collaborators': [],
  '/orgs/test-org/actions/permissions/workflow': {},
  '/orgs/test-org/actions/permissions/selected-actions': {},
  '/orgs/test-org/actions/secrets': { secrets: [] },
  '/orgs/test-org/actions/variables': { variables: [] },
  '/orgs/test-org/rulesets': [],

  // GraphQL responses mapped by query type
  graphql: {
    branchProtectionRules: {
      response: {
        repository: {
          branchProtectionRules: {
            nodes: [],
            pageInfo: { hasNextPage: false, endCursor: null },
          },
        },
      },
    },
    createBranchProtectionRule: {
      response: {
        createBranchProtectionRule: {
          branchProtectionRule: { id: 'fake-rule-id-123' },
        },
      },
    },
    updateBranchProtectionRule: {
      response: {
        updateBranchProtectionRule: {
          branchProtectionRule: { id: 'fake-rule-id-123' },
        },
      },
    },
    deleteBranchProtectionRule: {
      response: {
        deleteBranchProtectionRule: { clientMutationId: null },
      },
    },
  },
}
