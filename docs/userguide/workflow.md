# Workflow for Changes

The typical workflow for making changes to your GitHub organization using `otterdog` is pull-request based and consists of the following phases:

## 1. Prepare your change

1. **Find the configuration repository**:
   Identify the otterdog configuration repository for your GitHub organization
   (e.g. `.eclipsefdn`, `.repositories`, or similar).

2. **Fork the repository (if needed)**:
   If you do not have write access, fork the repository according to your corporate guidelines or to your personal GitHub account.
   If you do not have write access and forking is not allowed, contact the organization maintainers.

3. **Clone the repository**:
   Clone the configuration repository locally
   (e.g. `gh repo clone <org>/.eclipsefdn`).

4. **Create a feature branch**:
   Create a branch from `main` for your change
   (e.g. `git switch -c my-feature-branch`).

5. **Edit configuration files**:
   Make your changes in the configuration files.
   The main entry point is `otterdog/<org>.jsonnet`.
   See [examples and tutorials](index.md) and the [Reference](../reference/index.md).

6. **Commit your changes**:
   Commit with a clear and descriptive message.

## 2. Open a Pull Request

7. **Push your branch and open a PR**:
   Push your branch and open a Pull Request against the `main` branch of the configuration repository.

## 3. Review and validation

8. **Automated checks run**:
   Syntax validation and configuration diff analysis are executed automatically for the Pull Request.

9. **Request reviews**:
   Request reviews as required for the type of change.
   Mandatory reviewers are assigned automatically.

10. **Address review feedback**:
    Respond to review comments and update the Pull Request if necessary.

## 4. Merge and apply

11. **Merge the Pull Request**:
    Once approved, the Pull Request can be merged.
    This may be done by the reviewer or the author, see automated comments for details.
    The merge triggers otterdog to automatically apply the changes to the GitHub organization.
