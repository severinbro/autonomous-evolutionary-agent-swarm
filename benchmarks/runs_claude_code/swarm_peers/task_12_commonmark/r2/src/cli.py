"""Command-line entry point: ``python3 -m src.cli`` reads Markdown on stdin
and writes the rendered HTML to stdout."""

import sys

from src.render import render


def main(argv=None, stdin=None, stdout=None):
    if stdin is None:
        stdin = sys.stdin
    if stdout is None:
        stdout = sys.stdout
    buf = getattr(stdin, "buffer", None)
    if buf is not None:
        text = buf.read().decode("utf-8", errors="replace")
    else:
        text = stdin.read()
    html = render(text)
    out = getattr(stdout, "buffer", None)
    if out is not None:
        stdout.flush()
        out.write(html.encode("utf-8"))
        out.flush()
    else:
        stdout.write(html)
    return 0


if __name__ == "__main__":
    sys.exit(main())
