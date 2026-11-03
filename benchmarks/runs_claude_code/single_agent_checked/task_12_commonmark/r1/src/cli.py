"""Command line entry point: ``python3 -m src.cli < input.md > output.html``."""

import sys

from .render import render


def main(argv=None):
    data = sys.stdin.buffer.read().decode('utf-8', errors='replace')
    html = render(data)
    sys.stdout.buffer.write(html.encode('utf-8', errors='surrogatepass'))
    sys.stdout.flush()
    return 0


if __name__ == '__main__':
    sys.exit(main())
