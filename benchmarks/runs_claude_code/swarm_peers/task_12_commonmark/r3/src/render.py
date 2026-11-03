"""HTML rendering for CommonMark 0.31.2.

``render(markdown) -> str`` parses the block structure with
``src.blocks``, renders inline content with ``src.inlines`` and produces
HTML in the same form as the spec examples.
"""

from .blocks import parse_document
from .inlines import render_inlines

__all__ = ["render"]

_CONTAINERS = ("document", "block_quote", "list", "item")


def _escape(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


class _HtmlRenderer(object):

    def __init__(self, refmap):
        self.refmap = refmap
        self.buf = []
        self.last_out = "\n"

    def out(self, s):
        if s:
            self.buf.append(s)
            self.last_out = s[-1]

    def cr(self):
        if self.last_out != "\n":
            self.out("\n")

    def inlines(self, content):
        return render_inlines(content or "", self.refmap)

    def render_node(self, root):
        # Iterative walk (enter/exit events) so deeply nested documents do
        # not hit Python's recursion limit.
        stack = [(root, True)]
        while stack:
            node, entering = stack.pop()
            if entering:
                self.enter(node)
                if node.type in _CONTAINERS:
                    stack.append((node, False))
                    for child in reversed(node.children):
                        stack.append((child, True))
            else:
                self.exit(node)

    def enter(self, node):
        t = node.type
        if t == "paragraph":
            grandparent = node.parent.parent if node.parent else None
            if (grandparent is not None and grandparent.type == "list" and
                    grandparent.tight):
                self.out(self.inlines(node.content))
            else:
                self.cr()
                self.out("<p>")
                self.out(self.inlines(node.content))
                self.out("</p>")
                self.cr()
        elif t == "heading":
            tag = "h%d" % node.level
            self.cr()
            self.out("<%s>" % tag)
            self.out(self.inlines(node.content))
            self.out("</%s>" % tag)
            self.cr()
        elif t == "code_block":
            words = node.info.split() if node.info else []
            self.cr()
            self.out("<pre><code")
            if words:
                self.out(' class="language-%s"' % _escape(words[0]))
            self.out(">")
            self.out(_escape(node.literal or ""))
            self.out("</code></pre>")
            self.cr()
        elif t == "html_block":
            self.cr()
            self.out(node.literal or "")
            self.cr()
        elif t == "thematic_break":
            self.cr()
            self.out("<hr />")
            self.cr()
        elif t == "block_quote":
            self.cr()
            self.out("<blockquote>")
            self.cr()
        elif t == "list":
            tag = "ol" if node.ordered else "ul"
            self.cr()
            if node.ordered and node.start is not None and node.start != 1:
                self.out('<%s start="%d">' % (tag, node.start))
            else:
                self.out("<%s>" % tag)
            self.cr()
        elif t == "item":
            self.out("<li>")

    def exit(self, node):
        t = node.type
        if t == "block_quote":
            self.cr()
            self.out("</blockquote>")
            self.cr()
        elif t == "list":
            self.cr()
            self.out("</%s>" % ("ol" if node.ordered else "ul"))
            self.cr()
        elif t == "item":
            self.out("</li>")
            self.cr()

    def result(self):
        return "".join(self.buf)


def render(markdown):
    """Render a CommonMark document to HTML."""
    root, refmap = parse_document(markdown)
    renderer = _HtmlRenderer(refmap)
    renderer.render_node(root)
    return renderer.result()
