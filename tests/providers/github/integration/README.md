<!--
Copyright (c) 2026 Eclipse Foundation and others.
This program and the accompanying materials are made available
under the terms of the Eclipse Public License 2.0
which is available at http://www.eclipse.org/legal/epl-v20.html
SPDX-License-Identifier: EPL-2.0
-->

# Integration tests

Tests start from two model states (`old` → `new`) and treat the full flow from diff generation
to GitHub REST API calls, and back, as the system under test.

Because the relevant logic is spread across many units and files, small isolated unit tests
tend to provide limited value. These tests focus instead on validating that the system behaves
correctly when all parts interact.

The goal is stability: as long as the externally observable behavior is unchanged, these tests
should continue to pass even if internal code is refactored or redesigned. Assertions are
therefore limited to the rather stable model objects and the extremely stable GitHub HTTP API.

The tests do not validate internal steps or intermediate state. This makes failures
harder to localize, but keeps the suite robust and focused on user-visible behavior.
