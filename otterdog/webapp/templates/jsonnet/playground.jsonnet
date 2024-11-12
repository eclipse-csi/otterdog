local orgs = import '{{ default_config }}';

orgs.newRepo('myrepo') {
  has_issues: false,
}
