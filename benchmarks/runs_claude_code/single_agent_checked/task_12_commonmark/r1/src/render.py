"""HTML rendering for CommonMark documents.

``render(markdown)`` parses Markdown with the block and inline parsers and
produces HTML in the same form as the CommonMark 0.31.2 spec examples.
"""

import re

from .blocks import parse

_RE_INFO_SPLIT = re.compile(r'[ \t\n\r\f\v]+')


def escape_html(s):
    return (s.replace('&', '&amp;').replace('<', '&lt;')
            .replace('>', '&gt;').replace('"', '&quot;'))


class HtmlRenderer:
    def __init__(self):
        self.buffer = []
        self.last_out = '\n'
        self.disable_tags = 0

    # -- output primitives -------------------------------------------------
    def lit(self, s):
        self.buffer.append(s)
        self.last_out = s

    def out(self, s):
        self.lit(escape_html(s))

    def cr(self):
        if self.last_out != '\n':
            self.lit('\n')

    def tag(self, name, attrs=None, selfclosing=False):
        if self.disable_tags > 0:
            return
        parts = ['<', name]
        if attrs:
            for key, value in attrs:
                parts.append(' %s="%s"' % (key, value))
        if selfclosing:
            parts.append(' /')
        parts.append('>')
        self.lit(''.join(parts))

    # -- driver --------------------------------------------------------------
    def render(self, document):
        self.buffer = []
        self.last_out = '\n'
        self.disable_tags = 0
        for node, entering in document.walk():
            handler = getattr(self, 'r_' + node.type)
            handler(node, entering)
        return ''.join(self.buffer)

    # -- block nodes ---------------------------------------------------------
    def r_document(self, node, entering):
        pass

    def r_paragraph(self, node, entering):
        grandparent = node.parent.parent if node.parent is not None else None
        if (grandparent is not None and grandparent.type == 'list'
                and grandparent.list_data.tight):
            return
        if entering:
            self.cr()
            self.tag('p')
        else:
            self.tag('/p')
            self.cr()

    def r_heading(self, node, entering):
        name = 'h%d' % node.level
        if entering:
            self.cr()
            self.tag(name)
        else:
            self.tag('/' + name)
            self.cr()

    def r_block_quote(self, node, entering):
        if entering:
            self.cr()
            self.tag('blockquote')
            self.cr()
        else:
            self.cr()
            self.tag('/blockquote')
            self.cr()

    def r_list(self, node, entering):
        name = 'ul' if node.list_data.type == 'bullet' else 'ol'
        if entering:
            attrs = []
            start = node.list_data.start
            if start is not None and start != 1:
                attrs.append(('start', str(start)))
            self.cr()
            self.tag(name, attrs)
            self.cr()
        else:
            self.cr()
            self.tag('/' + name)
            self.cr()

    def r_item(self, node, entering):
        if entering:
            self.tag('li')
        else:
            self.tag('/li')
            self.cr()

    def r_thematic_break(self, node, entering):
        self.cr()
        self.tag('hr', None, True)
        self.cr()

    def r_code_block(self, node, entering):
        attrs = []
        info = node.info or ''
        words = _RE_INFO_SPLIT.split(info) if info else []
        if words and words[0]:
            attrs.append(('class', 'language-' + escape_html(words[0])))
        self.cr()
        self.tag('pre')
        self.tag('code', attrs)
        self.out(node.literal)
        self.tag('/code')
        self.tag('/pre')
        self.cr()

    def r_html_block(self, node, entering):
        self.cr()
        self.lit(node.literal)
        self.cr()

    # -- inline nodes --------------------------------------------------------
    def r_text(self, node, entering):
        self.out(node.literal)

    def r_softbreak(self, node, entering):
        self.lit('\n')

    def r_linebreak(self, node, entering):
        self.tag('br', None, True)
        self.cr()

    def r_code(self, node, entering):
        self.tag('code')
        self.out(node.literal)
        self.tag('/code')

    def r_html_inline(self, node, entering):
        self.lit(node.literal)

    def r_emph(self, node, entering):
        self.tag('em' if entering else '/em')

    def r_strong(self, node, entering):
        self.tag('strong' if entering else '/strong')

    def r_link(self, node, entering):
        if entering:
            attrs = [('href', escape_html(node.destination))]
            if node.title:
                attrs.append(('title', escape_html(node.title)))
            self.tag('a', attrs)
        else:
            self.tag('/a')

    def r_image(self, node, entering):
        if entering:
            if self.disable_tags == 0:
                self.lit('<img src="' + escape_html(node.destination) + '" alt="')
            self.disable_tags += 1
        else:
            self.disable_tags -= 1
            if self.disable_tags == 0:
                if node.title:
                    self.lit('" title="' + escape_html(node.title))
                self.lit('" />')


def render_document(document):
    return HtmlRenderer().render(document)


def render(markdown: str) -> str:
    """Render CommonMark markdown to HTML."""
    return HtmlRenderer().render(parse(markdown))
