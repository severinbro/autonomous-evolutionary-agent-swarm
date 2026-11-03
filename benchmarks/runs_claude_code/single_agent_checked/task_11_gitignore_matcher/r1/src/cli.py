"""CLI: python3 -m src.cli <gitignore_path> <path>...

Prints each ignored path (sorted) on its own line.
"""

from __future__ import annotations

import sys

from .matcher import GitIgnore


def main(argv=None) -> int:
    args = sys.argv[1:] if argv is None else list(argv)
    if not args:
        print("usage: python3 -m src.cli <gitignore_path> <path>...", file=sys.stderr)
        return 2
    gitignore_path, paths = args[0], args[1:]
    try:
        with open(gitignore_path, "r", encoding="utf-8", errors="surrogateescape",
                  newline="") as fh:
            text = fh.read()
    except OSError as exc:
        print(f"error: cannot read {gitignore_path}: {exc}", file=sys.stderr)
        return 2
    matcher = GitIgnore(text)
    for path in matcher.ignored_files(paths):
        print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
