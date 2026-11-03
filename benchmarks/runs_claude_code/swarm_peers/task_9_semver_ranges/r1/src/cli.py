"""Command-line entrypoint.

Usage:
    python3 -m src.cli satisfies <version> <range>   -> prints "true" / "false"
    python3 -m src.cli max <range> <version>...      -> prints the result or "null"

Arguments are read positionally (no option parsing), so ranges such as
"1.2.3 - 2.0.0" or versions beginning with "-" are passed through verbatim.
"""

import sys

from src.ranges import max_satisfying, satisfies

USAGE = (
    "usage: python3 -m src.cli satisfies <version> <range>\n"
    "       python3 -m src.cli max <range> <version>..."
)


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print(USAGE, file=sys.stderr)
        return 2
    command, rest = args[0], args[1:]
    if command == "satisfies":
        if len(rest) != 2:
            print(USAGE, file=sys.stderr)
            return 2
        print("true" if satisfies(rest[0], rest[1]) else "false")
        return 0
    if command == "max":
        if len(rest) < 1:
            print(USAGE, file=sys.stderr)
            return 2
        result = max_satisfying(rest[1:], rest[0])
        print("null" if result is None else result)
        return 0
    print(USAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
