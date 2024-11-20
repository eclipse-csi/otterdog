The following format is supported to match repositories to be included / excluded in organization rulesets:

| Description                           | Format                                                                                                                                                                                     | Example            |
|---------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|--------------------|
| match repositories by name or pattern | see [fnmatch syntax](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/creating-rulesets-for-a-repository#using-fnmatch-syntax) | `jdk*`, `otterdog` |
| match all repositories                | `~ALL`                                                                                                                                                                                     | `~ALL`             |
