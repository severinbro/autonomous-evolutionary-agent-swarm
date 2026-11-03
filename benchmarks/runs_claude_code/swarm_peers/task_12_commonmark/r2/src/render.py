"""HTML rendering for CommonMark 0.31.2.

``render(markdown) -> str`` parses the block structure with ``src.blocks``,
renders inline content with ``src.inlines.render_inlines`` and serialises the
result in the same form as the spec examples.
"""

import re

from . import blocks
from . import inlines

_RE_WS = re.compile(r'[ \t\n\r\x0b\x0c]+')


def _escape(s):
    return (s.replace('&', '&amp;').replace('<', '&lt;')
            .replace('>', '&gt;').replace('"', '&quot;'))


class _HtmlRenderer(object):

    def __init__(self, refmap):
        self.refmap = refmap
        self.buf = []
        self.last_out = '\n'

    def out(self, s):
        if s:
            self.buf.append(s)
            self.last_out = s

    def cr(self):
        if self.last_out[-1:] != '\n':
            self.out('\n')

    def inline(self, text):
        return inlines.render_inlines(text, self.refmap)

    def render_node(self, root):
        # Iterative walk (enter/exit events) so deeply nested input cannot
        # exhaust the Python recursion limit.
        stack = [(root, True)]
        while stack:
            node, entering = stack.pop()
            if entering:
                if self.enter(node):
                    stack.append((node, False))
                    for child in reversed(node.children):
                        stack.append((child, True))
            else:
                self.exit(node)

    def enter(self, node):
        """Emit the opening part of node; return True if it has children
        to walk (and an exit event)."""
        t = node.type
        if t == 'document':
            return True
        if t == 'paragraph':
            grandparent = node.parent.parent if node.parent is not None else None
            if grandparent is not None and grandparent.type == 'list' and \
                    grandparent.list_data['tight']:
                self.out(self.inline(node.content))
            else:
                self.cr()
                self.out('<p>')
                self.out(self.inline(node.content))
                self.out('</p>')
                self.cr()
            return False
        if t == 'heading':
            tag = 'h%d' % node.level
            self.cr()
            self.out('<%s>' % tag)
            self.out(self.inline(node.content))
            self.out('</%s>' % tag)
            self.cr()
            return False
        if t == 'code_block':
            words = _RE_WS.split(node.info) if node.info else []
            self.cr()
            if words and words[0]:
                self.out('<pre><code class="language-%s">' % _escape(words[0]))
            else:
                self.out('<pre><code>')
            self.out(_escape(node.literal))
            self.out('</code></pre>')
            self.cr()
            return False
        if t == 'html_block':
            self.cr()
            self.out(node.literal)
            self.cr()
            return False
        if t == 'thematic_break':
            self.cr()
            self.out('<hr />')
            self.cr()
            return False
        if t == 'block_quote':
            self.cr()
            self.out('<blockquote>')
            self.cr()
            return True
        if t == 'list':
            ld = node.list_data
            if ld['type'] == 'bullet':
                self.cr()
                self.out('<ul>')
            else:
                start = ld['start']
                attrs = '' if start is None or start == 1 else ' start="%d"' % start
                self.cr()
                self.out('<ol%s>' % attrs)
            self.cr()
            return True
        if t == 'item':
            self.out('<li>')
            return True
        return True

    def exit(self, node):
        t = node.type
        if t == 'block_quote':
            self.cr()
            self.out('</blockquote>')
            self.cr()
        elif t == 'list':
            self.cr()
            self.out('</ul>' if node.list_data['type'] == 'bullet' else '</ol>')
            self.cr()
        elif t == 'item':
            self.out('</li>')
            self.cr()

    def result(self):
        return ''.join(self.buf)


def render(markdown):
    """Render a CommonMark document to HTML."""
    doc, refmap = blocks.parse(markdown)
    r = _HtmlRenderer(refmap)
    r.render_node(doc)
    return r.result()
