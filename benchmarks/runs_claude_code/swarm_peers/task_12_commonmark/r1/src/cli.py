"""CLI: ``python3 -m src.cli`` reads Markdown from stdin, writes HTML to stdout."""

import sys

from .render import render


def main(argv=None) -> int:
    data = sys.stdin.buffer.read()
    text = data.decode("utf-8", errors="replace")
    html = render(text)
    out = getattr(sys.stdout, "buffer", None)
    if out is not None:
        out.write(html.encode("utf-8"))
        out.flush()
    else:
        sys.stdout.write(html)
    return 0


if __name__ == "__main__":
    sys.exit(main())
