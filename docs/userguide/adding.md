In order to add new resources to a given GitHub organization, the resources have to be declared at the correct
location in the jsonnet configuration file (see supported [Resources](../../reference/organization)).

The resource has to be created with its corresponding jsonnet function as described in the respective section
in the reference guide. By default, all parameter values as defined in the default configuration are inherited,
but can be overwritten as needed.

## Adding a new repository

For example, we already have a GitHub organization `testorg` that already has a repository `existing-repo`:

``` jsonnet
orgs.newOrg('testorg') {
  ...
  _repositories+:: [
    ...
    orgs.newRepo('existing-repo') {
      description: "My first test repo",
      allow_auto_merge: true,
      ...
    },
}
```

Now we would like to add another repo with some specific settings that are different from the default config.
Thus, we use the template function for creating a new repository `newRepo` and overwrite settings as needed.

``` jsonnet
orgs.newRepo('new-repo') {
  description: "My second test repo",
  allow_auto_merge: true,
  allow_merge_commit: false,
  allow_update_branch: false,
  dependabot_alerts_enabled: false,
  ...
}
```

!!! note

    Otterdog comes with a builtin Playground to try out snippets and inspect the final manifestation
    of settings depending on the default configuration in use. Check the Dashboard of your project
    for further details.

Finally, we need to add this snippet to the existing configuration, adding it to the `_repositories` key in the
configuration file:

``` diff
orgs.newOrg('testorg') {
  ...
  _repositories+:: [
    ...
    orgs.newRepo('existing-repo') {
      description: "My first test repo",
      allow_auto_merge: true,
      ...
    },
+   orgs.newRepo('new-repo') {
+     description: "My second test repo",
+     allow_auto_merge: true,
+     allow_merge_commit: false,
+     allow_update_branch: false,
+     dependabot_alerts_enabled: false,
+     ...
+   },
}
```
