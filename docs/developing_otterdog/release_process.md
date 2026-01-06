# Release Process

The release process is performed by committers following these steps:

1. **Update CHANGELOG.md**: Create a PR updating the [`CHANGELOG.md`](https://github.com/eclipse-csi/otterdog/blob/main/CHANGELOG.md) file

    - Ensure all changes are documented

        !!! note

            - If new features are added: bump the semver minor version (e.g., 1.2.0 → 1.3.0)
            - If breaking compatibility changes are introduced: bump the semver major version (e.g., 1.2.0 → 2.0.0)
            - For bug fixes only: bump the patch version (e.g., 1.2.0 → 1.2.1)

    - Add the release date to the version that is currently marked as unreleased
    - [Optional] Add the new unreleased version


2. **Create and Push Tag**:

    - Create a new tag (signing is recommended):
        ```bash
        git tag -s v1.2.3 -m "Release version 1.2.3"
        ```
    - Push the tag to the repository:
        ```bash
        git push origin v1.2.3
        ```
