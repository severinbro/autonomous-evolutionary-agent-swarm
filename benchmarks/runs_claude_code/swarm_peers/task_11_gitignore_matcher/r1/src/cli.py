"""Command-line entry point.

Usage: python3 -m src.cli <gitignore_path> <path>...

Prints every ignored path (sorted) on its own line.
"""

import sys

from src.matcher import GitIgnore


USAGE = "usage: python3 -m src.cli <gitignore_path> <path>..."


def read_gitignore(gitignore_path):
    """Return the exact text of the .gitignore file (no newline translation)."""
    with open(gitignore_path, "r", encoding="utf-8", errors="surrogateescape",
              newline="") as fh:
        return fh.read()


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    argv = list(argv)
    if len(argv) < 1:
        print(USAGE, file=sys.stderr)
        return 2
    gitignore_path, paths = argv[0], argv[1:]
    try:
        text = read_gitignore(gitignore_path)
    except OSError as exc:
        print("error: cannot read %s: %s" % (gitignore_path, exc), file=sys.stderr)
        return 2
    matcher = GitIgnore(text)
    for path in matcher.ignored_files(paths):
        sys.stdout.write(path + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
