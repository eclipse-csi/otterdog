local orgs = import '{{ default_config }}';

orgs.newOrg('my-project', 'my-org') {
  _repositories+:: [
    orgs.newRepo('myrepo') {
      has_issues: false,
    },
  ],
}
