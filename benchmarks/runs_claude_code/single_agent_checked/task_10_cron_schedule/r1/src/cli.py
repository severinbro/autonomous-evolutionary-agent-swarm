"""CLI: python3 -m src.cli "<expr>" <iso-datetime> [n]"""

import sys
from datetime import datetime

from .schedule import next_fires


def main(argv=None):
    args = sys.argv[1:] if argv is None else list(argv)
    if len(args) not in (2, 3):
        print('usage: python3 -m src.cli "<expr>" <iso-datetime> [n]', file=sys.stderr)
        return 2
    try:
        after = datetime.fromisoformat(args[1])
        n = int(args[2]) if len(args) == 3 else 1
        fires = next_fires(args[0], after, n)
    except (ValueError, TypeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    for fire in fires:
        print(fire.isoformat())
    return 0


if __name__ == "__main__":
    sys.exit(main())
