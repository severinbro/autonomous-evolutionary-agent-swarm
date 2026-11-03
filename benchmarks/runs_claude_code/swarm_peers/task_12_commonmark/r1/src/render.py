"""Public entry point: CommonMark (0.31.2) Markdown -> HTML."""

from .blocks import parse_document, render_blocks


def render(markdown: str) -> str:
    """Render ``markdown`` to HTML as the CommonMark reference implementation does."""
    if not isinstance(markdown, str):
        raise TypeError("render() expects a str")
    root, refmap = parse_document(markdown)
    return render_blocks(root, refmap)


__all__ = ["render"]
