"""Command-line interface.

Usage:
    python3 -m src.cli satisfies <version> <range>    -> prints true/false
    python3 -m src.cli max <range> <version>...       -> prints version or null
"""

import sys

try:
    from .ranges import max_satisfying, satisfies
except ImportError:  # pragma: no cover - allows running as a plain script
    from ranges import max_satisfying, satisfies  # type: ignore

USAGE = ("usage: python3 -m src.cli satisfies <version> <range>\n"
         "       python3 -m src.cli max <range> <version>...")


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) == 3 and args[0] == "satisfies":
        print("true" if satisfies(args[1], args[2]) else "false")
        return 0
    if len(args) >= 2 and args[0] == "max":
        result = max_satisfying(args[2:], args[1])
        print("null" if result is None else result)
        return 0
    print(USAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
