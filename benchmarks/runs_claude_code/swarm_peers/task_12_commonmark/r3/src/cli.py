"""CLI entrypoint: ``python3 -m src.cli`` reads Markdown from stdin, writes HTML to stdout."""
import sys

from src.render import render


def main(argv=None):
    data = sys.stdin.buffer.read().decode("utf-8", errors="replace")
    out = render(data)
    sys.stdout.buffer.write(out.encode("utf-8"))
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
