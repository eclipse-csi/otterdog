#  *******************************************************************************
#  Copyright (c) 2023-2025 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

# values made of characters a shell would treat as syntax rather than as literal text
SHELL_METACHARACTER_VALUES = [
    "$(echo substituted)",
    "a; echo chained",
    "a && echo conjoined",
    "a | echo piped",
    "a`echo backticked`",
    "a\necho newline",
    "a 2>/dev/null; echo redirected",
]
