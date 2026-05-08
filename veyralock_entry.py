"""Combined Windows entry point for the VeyraLock CLI and GUI."""

from __future__ import annotations

import sys


def main() -> int:
    """Dispatch to the GUI when no CLI args are given, otherwise run the CLI."""
    if len(sys.argv) == 1:
        from veyralock.gui import main as gui_main

        return gui_main()

    if len(sys.argv) > 1 and sys.argv[1] == "--gui":
        sys.argv.pop(1)
        from veyralock.gui import main as gui_main

        return gui_main()

    from veyralock.cli import main as cli_main

    return cli_main()


if __name__ == "__main__":
    raise SystemExit(main())
