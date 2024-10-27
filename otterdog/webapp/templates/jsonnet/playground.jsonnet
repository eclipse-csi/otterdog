local orgs = import 'otterdog-defaults.libsonnet';

orgs.newRepo('myrepo') {
  has_issues: false,
}
