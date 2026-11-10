#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import sys

# the exit code of a process interrupted by SIGINT, by convention 128 + the signal number
EXIT_CODE_INTERRUPTED = 130


def main() -> None:
    """
    Entry point of the command line interface.

    Loading the cli imports all dependencies of otterdog, which takes a noticeable time. An interrupt (Ctrl+C) during
    that time is reported like the interrupts handled by click once the cli is running, instead of with a traceback.
    This module must therefore not import anything that is not part of the standard library.
    """
    try:
        from otterdog.cli import cli

        cli()
    except KeyboardInterrupt:
        sys.stderr.write("\nAborted!\n")
        sys.exit(EXIT_CODE_INTERRUPTED)


if __name__ == "__main__":
    main()
