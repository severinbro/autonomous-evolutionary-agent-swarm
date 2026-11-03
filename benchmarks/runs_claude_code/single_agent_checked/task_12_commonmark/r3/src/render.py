"""HTML rendering for CommonMark documents."""
from .blocks import BlockParser
from .common import escape_html

__all__ = ['render', 'parse', 'HtmlRenderer']


def parse(markdown):
    """Parse markdown text into a document tree."""
    return BlockParser().parse(markdown)


class HtmlRenderer:
    def __init__(self):
        self.buf = []
        self.last_out = '\n'
        self.alt_depth = 0

    def lit(self, s):
        if s:
            self.buf.append(s)
            self.last_out = s[-1]

    def cr(self):
        if self.last_out != '\n':
            self.lit('\n')

    def render(self, doc):
        self.buf = []
        self.last_out = '\n'
        self.alt_depth = 0
        for node, entering in doc.walk():
            self.render_node(node, entering)
        return ''.join(self.buf)

    def render_node(self, node, entering):
        t = node.type
        if self.alt_depth > 0:
            # Inside an image description: emit plain text only.
            if t in ('text', 'code', 'html_inline'):
                self.lit(escape_html(node.literal))
            elif t in ('softbreak', 'linebreak'):
                self.lit(' ')
            elif t == 'image':
                if entering:
                    self.alt_depth += 1
                else:
                    self.alt_depth -= 1
                    if self.alt_depth == 0:
                        self._close_image(node)
            return
        if t == 'document':
            return
        if t == 'text':
            self.lit(escape_html(node.literal))
        elif t == 'softbreak':
            self.lit('\n')
        elif t == 'linebreak':
            self.lit('<br />\n')
        elif t == 'emph':
            self.lit('<em>' if entering else '</em>')
        elif t == 'strong':
            self.lit('<strong>' if entering else '</strong>')
        elif t == 'code':
            self.lit('<code>' + escape_html(node.literal) + '</code>')
        elif t == 'html_inline':
            self.lit(node.literal)
        elif t == 'link':
            if entering:
                s = '<a href="' + escape_html(node.destination) + '"'
                if node.title:
                    s += ' title="' + escape_html(node.title) + '"'
                self.lit(s + '>')
            else:
                self.lit('</a>')
        elif t == 'image':
            if entering:
                self.lit('<img src="' + escape_html(node.destination) + '" alt="')
                self.alt_depth += 1
                # The matching exit event is handled in the alt-text branch
                # above, which closes the tag once alt_depth returns to 0.
        elif t == 'paragraph':
            grandparent = node.parent.parent if node.parent else None
            tight = (grandparent is not None and grandparent.type == 'list'
                     and grandparent.list_data.tight)
            if tight:
                return
            if entering:
                self.cr()
                self.lit('<p>')
            else:
                self.lit('</p>')
                self.cr()
        elif t == 'heading':
            tag = 'h%d' % node.level
            if entering:
                self.cr()
                self.lit('<' + tag + '>')
            else:
                self.lit('</' + tag + '>')
                self.cr()
        elif t == 'thematic_break':
            self.cr()
            self.lit('<hr />')
            self.cr()
        elif t == 'block_quote':
            if entering:
                self.cr()
                self.lit('<blockquote>')
                self.cr()
            else:
                self.cr()
                self.lit('</blockquote>')
                self.cr()
        elif t == 'list':
            ld = node.list_data
            tag = 'ul' if ld.type == 'bullet' else 'ol'
            if entering:
                self.cr()
                if tag == 'ol' and ld.start is not None and ld.start != 1:
                    self.lit('<ol start="%d">' % ld.start)
                else:
                    self.lit('<' + tag + '>')
                self.cr()
            else:
                self.cr()
                self.lit('</' + tag + '>')
                self.cr()
        elif t == 'item':
            if entering:
                self.cr()
                self.lit('<li>')
            else:
                self.lit('</li>')
                self.cr()
        elif t == 'code_block':
            info_words = node.info.split() if node.info else []
            self.cr()
            if info_words:
                self.lit('<pre><code class="language-' +
                         escape_html(info_words[0]) + '">')
            else:
                self.lit('<pre><code>')
            self.lit(escape_html(node.literal))
            self.lit('</code></pre>')
            self.cr()
        elif t == 'html_block':
            self.cr()
            self.lit(node.literal)
            self.cr()

    def _close_image(self, node):
        s = '"'
        if node.title:
            s += ' title="' + escape_html(node.title) + '"'
        self.lit(s + ' />')


def render(markdown):
    """Render CommonMark markdown text to HTML."""
    return HtmlRenderer().render(parse(markdown))
