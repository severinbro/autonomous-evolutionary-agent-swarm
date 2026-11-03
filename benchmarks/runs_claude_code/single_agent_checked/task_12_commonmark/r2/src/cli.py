"""Command line entry point: ``python3 -m src.cli < input.md > output.html``."""

import io
import sys

from .render import render


def main(argv=None, stdin=None, stdout=None):
    if stdin is None:
        stdin = io.TextIOWrapper(sys.stdin.buffer, encoding='utf-8',
                                 errors='replace', newline='')
    text = stdin.read()
    html = render(text)
    if stdout is None:
        sys.stdout.buffer.write(html.encode('utf-8'))
        sys.stdout.buffer.flush()
    else:
        stdout.write(html)
        stdout.flush()
    return 0


if __name__ == '__main__':
    sys.exit(main())
