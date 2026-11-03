"""Command-line entry point: read Markdown on stdin, write HTML to stdout.

Usage: python3 -m src.cli < input.md > output.html
"""
import sys

from .render import render


def main(argv=None):
    data = sys.stdin.buffer.read()
    text = data.decode('utf-8', errors='replace')
    if text.startswith('﻿'):
        text = text[1:]
    html = render(text)
    sys.stdout.buffer.write(html.encode('utf-8'))
    sys.stdout.buffer.flush()
    return 0


if __name__ == '__main__':
    sys.exit(main())
