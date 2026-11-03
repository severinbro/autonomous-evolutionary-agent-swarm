"""Block-structure parsing for CommonMark 0.31.2.

Public API:
    parse(markdown: str) -> (doc: Node, refmap: dict)

The returned tree consists of ``Node`` objects with ``type`` one of:
document, block_quote, list, item, paragraph, heading, code_block,
html_block, thematic_break.

Leaf content:
    paragraph / heading : ``node.content`` -- raw inline text (stripped)
    code_block          : ``node.literal`` (text), ``node.info`` (unescaped info string, '' if none)
    html_block          : ``node.literal``
    heading             : ``node.level``
    list                : ``node.list_data`` dict (type, start, tight, bullet_char, delimiter, ...)

refmap maps normalized label -> (destination, title_or_None); destination and
title have backslash escapes and entities already processed.
"""

import re

from .inlines import normalize_label, unescape_string

CODE_INDENT = 4

_TAGNAME = r'[A-Za-z][A-Za-z0-9-]*'
_ATTRIBUTENAME = r'[a-zA-Z_:][a-zA-Z0-9:._-]*'
_UNQUOTEDVALUE = r'[^"\'=<>`\x00-\x20]+'
_SINGLEQUOTEDVALUE = r"'[^']*'"
_DOUBLEQUOTEDVALUE = r'"[^"]*"'
_ATTRIBUTEVALUE = '(?:' + _UNQUOTEDVALUE + '|' + _SINGLEQUOTEDVALUE + '|' + _DOUBLEQUOTEDVALUE + ')'
_WS = r'[ \t\n\x0b\x0c\r]'
_ATTRIBUTEVALUESPEC = '(?:' + _WS + '*=' + _WS + '*' + _ATTRIBUTEVALUE + ')'
_ATTRIBUTE = '(?:' + _WS + '+' + _ATTRIBUTENAME + _ATTRIBUTEVALUESPEC + '?)'
_OPENTAG = '<' + _TAGNAME + _ATTRIBUTE + '*' + _WS + '*/?>'
_CLOSETAG = '</' + _TAGNAME + _WS + '*>'

_BLOCK_TAGS = (
    'address|article|aside|base|basefont|blockquote|body|caption|center|col|'
    'colgroup|dd|details|dialog|dir|div|dl|dt|fieldset|figcaption|figure|'
    'footer|form|frame|frameset|h[123456]|head|header|hr|html|iframe|legend|'
    'li|link|main|menu|menuitem|nav|noframes|ol|optgroup|option|p|param|'
    'search|section|summary|table|tbody|td|tfoot|th|thead|title|tr|track|ul'
)

RE_HTML_BLOCK_OPEN = [
    None,
    re.compile(r'<(?:script|pre|textarea|style)(?:[ \t\n\x0b\x0c\r]|>|$)', re.I),
    re.compile(r'<!--'),
    re.compile(r'<[?]'),
    re.compile(r'<![A-Za-z]'),
    re.compile(r'<!\[CDATA\['),
    re.compile(r'</?(?:' + _BLOCK_TAGS + r')(?:[ \t\n\x0b\x0c\r]|/?>|$)', re.I),
    re.compile('(?!</?(?:script|style|pre|textarea)(?![A-Za-z0-9-]))'
               '(?:' + _OPENTAG + '|' + _CLOSETAG + ')[ \t]*$', re.I),
]

RE_HTML_BLOCK_CLOSE = [
    None,
    re.compile(r'</(?:script|pre|textarea|style)>', re.I),
    re.compile(r'-->'),
    re.compile(r'\?>'),
    re.compile(r'>'),
    re.compile(r'\]\]>'),
]

RE_MAYBE_SPECIAL = re.compile(r'[#`~*+_=<>0-9-]')
RE_NON_SPACE = re.compile(r'[^ \t\f\v\r\n]')
RE_BULLET_LIST_MARKER = re.compile(r'[*+-]')
RE_ORDERED_LIST_MARKER = re.compile(r'(\d{1,9})([.)])')
RE_ATX_HEADING_MARKER = re.compile(r'#{1,6}(?:[ \t]+|$)')
RE_CODE_FENCE = re.compile(r'`{3,}(?!.*`)|~{3,}')
RE_CLOSING_CODE_FENCE = re.compile(r'(?:`{3,}|~{3,})(?=[ \t]*$)')
RE_SETEXT_HEADING_LINE = re.compile(r'(?:=+|-+)[ \t]*$')
RE_THEMATIC_BREAK = re.compile(r'(?:(?:\*[ \t]*){3,}|(?:_[ \t]*){3,}|(?:-[ \t]*){3,})$')
RE_LINE_ENDING = re.compile(r'\r\n|\r|\n')
RE_TRAILING_BLANK_LINES = re.compile(r'(\n *)+$')

# Link reference definition pieces
RE_LINK_LABEL = re.compile(r'\[(?:[^\\\[\]]|\\.){0,1000}\]', re.S)
RE_LINK_DEST_BRACES = re.compile(r'<(?:[^<>\n\\\x00]|\\.)*>', re.S)
_ESCAPABLE = '[!"#$%&\'()*+,./:;<=>?@\\[\\\\\\]^_`{|}~-]'
_ESCAPED_CHAR = '\\\\' + _ESCAPABLE
RE_LINK_TITLE = re.compile(
    '(?:"(?:' + _ESCAPED_CHAR + '|\\\\[^\\\\]|[^\\\\"\\x00])*"'
    + "|'(?:" + _ESCAPED_CHAR + "|\\\\[^\\\\]|[^\\\\'\\x00])*'"
    + '|\\((?:' + _ESCAPED_CHAR + '|\\\\[^\\\\]|[^\\\\()\\x00])*\\))', re.S)
RE_SPNL = re.compile(r'[ \t]*(?:\n[ \t]*)?')
RE_SPACE_AT_END_OF_LINE = re.compile(r'[ \t]*(?:\n|$)')
RE_ESCAPABLE_CHAR = re.compile(_ESCAPABLE)


class Node(object):
    __slots__ = (
        'type', 'children', 'parent', 'open', 'start_line', 'start_col',
        'end_line', 'end_col', 'string_content', 'content', 'literal', 'info',
        'level', 'list_data', 'is_fenced', 'fence_char', 'fence_length',
        'fence_offset', 'html_block_type',
    )

    def __init__(self, type_, start_line=0, start_col=0):
        self.type = type_
        self.children = []
        self.parent = None
        self.open = True
        self.start_line = start_line
        self.start_col = start_col
        self.end_line = 0
        self.end_col = 0
        self.string_content = ''
        self.content = None
        self.literal = None
        self.info = None
        self.level = None
        self.list_data = None
        self.is_fenced = False
        self.fence_char = None
        self.fence_length = 0
        self.fence_offset = 0
        self.html_block_type = None

    @property
    def last_child(self):
        return self.children[-1] if self.children else None

    @property
    def first_child(self):
        return self.children[0] if self.children else None

    def append_child(self, child):
        child.parent = self
        self.children.append(child)

    def unlink(self):
        if self.parent is not None:
            self.parent.children.remove(self)
            self.parent = None

    def insert_after(self, sibling):
        parent = self.parent
        idx = parent.children.index(self)
        parent.children.insert(idx + 1, sibling)
        sibling.parent = parent

    def next_sibling(self):
        if self.parent is None:
            return None
        sibs = self.parent.children
        idx = sibs.index(self)
        return sibs[idx + 1] if idx + 1 < len(sibs) else None

    def __repr__(self):
        return 'Node(%s)' % self.type


def _peek(s, pos):
    return s[pos] if pos < len(s) else ''


def _is_space_or_tab(c):
    return c == ' ' or c == '\t'


def _is_blank(s):
    return RE_NON_SPACE.search(s) is None


# ---------------------------------------------------------------------------
# Link reference definitions
# ---------------------------------------------------------------------------

def _scan_link_destination(s, pos):
    """Return (raw_destination, newpos) or None."""
    m = RE_LINK_DEST_BRACES.match(s, pos)
    if m:
        return s[pos + 1:m.end() - 1], m.end()
    if _peek(s, pos) == '<':
        return None
    start = pos
    openparens = 0
    n = len(s)
    c = ''
    while pos < n:
        c = s[pos]
        if c == '\\' and pos + 1 < n and RE_ESCAPABLE_CHAR.match(s[pos + 1]):
            pos += 2
        elif c == '(':
            openparens += 1
            pos += 1
        elif c == ')':
            if openparens < 1:
                break
            openparens -= 1
            pos += 1
        elif ord(c) <= 0x20 or ord(c) == 0x7f:
            break
        else:
            pos += 1
    else:
        c = ''
    if pos == start and c != ')':
        return None
    if openparens != 0:
        return None
    return s[start:pos], pos


def parse_reference(s, refmap):
    """Try to parse a link reference definition at the start of s.

    Returns the number of characters consumed (0 if none)."""
    m = RE_LINK_LABEL.match(s, 0)
    if not m:
        return 0
    rawlabel = s[1:m.end() - 1]
    pos = m.end()
    if _peek(s, pos) != ':':
        return 0
    pos += 1
    pos = RE_SPNL.match(s, pos).end()
    res = _scan_link_destination(s, pos)
    if res is None:
        return 0
    dest, pos = res
    beforetitle = pos
    pos = RE_SPNL.match(s, pos).end()
    title = None
    if pos != beforetitle:
        tm = RE_LINK_TITLE.match(s, pos)
        if tm:
            title = s[pos + 1:tm.end() - 1]
            pos = tm.end()
    if title is None:
        pos = beforetitle
    at_line_end = True
    em = RE_SPACE_AT_END_OF_LINE.match(s, pos)
    if em is None:
        if title is None:
            at_line_end = False
        else:
            title = None
            pos = beforetitle
            em = RE_SPACE_AT_END_OF_LINE.match(s, pos)
            at_line_end = em is not None
    if not at_line_end:
        return 0
    pos = em.end()
    normlabel = normalize_label(rawlabel)
    if normlabel == '':
        return 0
    if normlabel not in refmap:
        refmap[normlabel] = (
            unescape_string(dest),
            unescape_string(title) if title is not None else None,
        )
    return pos


def _parse_references(content, refmap):
    """Strip leading link reference definitions from content."""
    found = False
    while content.startswith('['):
        pos = parse_reference(content, refmap)
        if not pos:
            break
        content = content[pos:]
        found = True
    return content, found


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def _can_contain(parent_type, child_type):
    if parent_type in ('document', 'block_quote', 'item'):
        return child_type != 'item'
    if parent_type == 'list':
        return child_type == 'item'
    return False


def _accepts_lines(t):
    return t in ('paragraph', 'code_block', 'html_block')


def _any_gap(nodes):
    """True if a blank line separates any two consecutive nodes."""
    for i in range(len(nodes) - 1):
        if nodes[i].end_line != nodes[i + 1].start_line - 1:
            return True
    return False


class BlockParser(object):

    def __init__(self):
        self.doc = Node('document', 1, 1)
        self.tip = self.doc
        self.oldtip = self.doc
        self.refmap = {}
        self.line_number = 0
        self.last_line_length = 0
        self.offset = 0
        self.column = 0
        self.next_nonspace = 0
        self.next_nonspace_column = 0
        self.indent = 0
        self.indented = False
        self.blank = False
        self.partially_consumed_tab = False
        self.all_closed = True
        self.last_matched_container = self.doc
        self.current_line = ''

    # -- low level helpers -------------------------------------------------

    def find_next_nonspace(self):
        line = self.current_line
        i = self.offset
        cols = self.column
        n = len(line)
        c = ''
        while i < n:
            c = line[i]
            if c == ' ':
                i += 1
                cols += 1
            elif c == '\t':
                i += 1
                cols += 4 - (cols % 4)
            else:
                break
        else:
            c = ''
        self.blank = c in ('', '\n', '\r')
        self.next_nonspace = i
        self.next_nonspace_column = cols
        self.indent = cols - self.column
        self.indented = self.indent >= CODE_INDENT

    def advance_next_nonspace(self):
        self.offset = self.next_nonspace
        self.column = self.next_nonspace_column
        self.partially_consumed_tab = False

    def advance_offset(self, count, columns=False):
        line = self.current_line
        n = len(line)
        while count > 0 and self.offset < n:
            c = line[self.offset]
            if c == '\t':
                chars_to_tab = 4 - (self.column % 4)
                if columns:
                    self.partially_consumed_tab = chars_to_tab > count
                    chars_to_advance = count if chars_to_tab > count else chars_to_tab
                    self.column += chars_to_advance
                    if not self.partially_consumed_tab:
                        self.offset += 1
                    count -= chars_to_advance
                else:
                    self.partially_consumed_tab = False
                    self.column += chars_to_tab
                    self.offset += 1
                    count -= 1
            else:
                self.partially_consumed_tab = False
                self.offset += 1
                self.column += 1
                count -= 1

    def add_line(self):
        if self.partially_consumed_tab:
            self.offset += 1
            chars_to_tab = 4 - (self.column % 4)
            self.tip.string_content += ' ' * chars_to_tab
        self.tip.string_content += self.current_line[self.offset:] + '\n'

    def add_child(self, tag, offset):
        while not _can_contain(self.tip.type, tag):
            self.finalize(self.tip, self.line_number - 1)
        node = Node(tag, self.line_number, offset + 1)
        self.tip.append_child(node)
        self.tip = node
        return node

    def close_unmatched_blocks(self):
        if not self.all_closed:
            while self.oldtip is not self.last_matched_container:
                parent = self.oldtip.parent
                self.finalize(self.oldtip, self.line_number - 1)
                self.oldtip = parent
            self.all_closed = True

    # -- continuation ------------------------------------------------------

    def _continue(self, container):
        t = container.type
        if t == 'document' or t == 'list':
            return 0
        if t == 'block_quote':
            line = self.current_line
            if not self.indented and _peek(line, self.next_nonspace) == '>':
                self.advance_next_nonspace()
                self.advance_offset(1, False)
                if _is_space_or_tab(_peek(line, self.offset)):
                    self.advance_offset(1, True)
                return 0
            return 1
        if t == 'item':
            ld = container.list_data
            if self.blank:
                if not container.children:
                    return 1
                self.advance_next_nonspace()
            elif self.indent >= ld['marker_offset'] + ld['padding']:
                self.advance_offset(ld['marker_offset'] + ld['padding'], True)
            else:
                return 1
            return 0
        if t in ('heading', 'thematic_break'):
            return 1
        if t == 'code_block':
            line = self.current_line
            indent = self.indent
            if container.is_fenced:
                m = None
                if indent <= 3 and _peek(line, self.next_nonspace) == container.fence_char:
                    m = RE_CLOSING_CODE_FENCE.match(line, self.next_nonspace)
                if m and (m.end() - m.start()) >= container.fence_length:
                    self.last_line_length = self.offset + indent + (m.end() - m.start())
                    self.finalize(container, self.line_number)
                    return 2
                i = container.fence_offset
                while i > 0 and _is_space_or_tab(_peek(line, self.offset)):
                    self.advance_offset(1, True)
                    i -= 1
            else:
                if indent >= CODE_INDENT:
                    self.advance_offset(CODE_INDENT, True)
                elif self.blank:
                    self.advance_next_nonspace()
                else:
                    return 1
            return 0
        if t == 'html_block':
            if self.blank and container.html_block_type in (6, 7):
                return 1
            return 0
        if t == 'paragraph':
            return 1 if self.blank else 0
        return 0

    # -- finalization ------------------------------------------------------

    def finalize(self, block, line_number):
        above = block.parent
        block.open = False
        block.end_line = line_number
        block.end_col = self.last_line_length
        t = block.type
        if t == 'paragraph':
            content, found = _parse_references(block.string_content, self.refmap)
            block.string_content = content
            if found and _is_blank(content):
                block.unlink()
        elif t == 'code_block':
            if not block.is_fenced:
                self._exclude_trailing_blank_lines(block)
            if block.is_fenced:
                content = block.string_content
                nl = content.find('\n')
                first_line = content[:nl]
                rest = content[nl + 1:]
                block.info = unescape_string(first_line.strip(' \t\n\r\x0b\x0c'))
                block.literal = rest
            else:
                block.literal = RE_TRAILING_BLANK_LINES.sub('\n', block.string_content)
            block.string_content = ''
        elif t == 'html_block':
            self._exclude_trailing_blank_lines(block)
            block.literal = RE_TRAILING_BLANK_LINES.sub('', block.string_content)
            block.string_content = ''
        elif t == 'item':
            if block.children:
                block.end_line = block.children[-1].end_line
                block.end_col = block.children[-1].end_col
            else:
                block.end_line = block.start_line
                ld = block.list_data
                block.end_col = ld['marker_offset'] + ld['padding']
        elif t == 'list':
            tight = not _any_gap(block.children)
            if tight:
                for item in block.children:
                    if _any_gap(item.children):
                        tight = False
                        break
            block.list_data['tight'] = tight
            if block.children:
                block.end_line = block.children[-1].end_line
                block.end_col = block.children[-1].end_col
        self.tip = above

    @staticmethod
    def _exclude_trailing_blank_lines(block):
        # Blank lines absorbed at the end of an indented code block or HTML
        # block count as "ending with a blank line" for list tightness.
        lines = block.string_content.split('\n')[:-1]
        count = 0
        for line in reversed(lines):
            if line.strip(' \t') == '':
                count += 1
            else:
                break
        if count:
            block.end_line -= count

    # -- block starts ------------------------------------------------------

    def _parse_list_marker(self, container):
        line = self.current_line
        rest_start = self.next_nonspace
        data = {
            'type': None,
            'tight': True,
            'bullet_char': None,
            'start': None,
            'delimiter': None,
            'padding': None,
            'marker_offset': self.indent,
        }
        if self.indent >= 4:
            return None
        m = RE_BULLET_LIST_MARKER.match(line, rest_start)
        if m:
            data['type'] = 'bullet'
            data['bullet_char'] = m.group(0)[0]
        else:
            m = RE_ORDERED_LIST_MARKER.match(line, rest_start)
            if m and (container.type != 'paragraph' or int(m.group(1)) == 1):
                data['type'] = 'ordered'
                data['start'] = int(m.group(1))
                data['delimiter'] = m.group(2)
            else:
                return None
        mlen = m.end() - m.start()
        nextc = _peek(line, self.next_nonspace + mlen)
        if not (nextc == '' or nextc == '\t' or nextc == ' '):
            return None
        if container.type == 'paragraph' and \
                not RE_NON_SPACE.search(line[self.next_nonspace + mlen:]):
            return None
        self.advance_next_nonspace()
        self.advance_offset(mlen, True)
        spaces_start_col = self.column
        spaces_start_offset = self.offset
        while True:
            self.advance_offset(1, True)
            nextc = _peek(line, self.offset)
            if not (self.column - spaces_start_col < 5 and _is_space_or_tab(nextc)):
                break
        blank_item = _peek(line, self.offset) == ''
        spaces_after_marker = self.column - spaces_start_col
        if spaces_after_marker >= 5 or spaces_after_marker < 1 or blank_item:
            data['padding'] = mlen + 1
            self.column = spaces_start_col
            self.offset = spaces_start_offset
            self.partially_consumed_tab = False
            if _is_space_or_tab(_peek(line, self.offset)):
                self.advance_offset(1, True)
        else:
            data['padding'] = mlen + spaces_after_marker
        return data

    def _try_block_starts(self, container):
        """Return (result, container). result 0 = no match, 1 = container,
        2 = leaf."""
        line = self.current_line
        nn = self.next_nonspace
        c = _peek(line, nn)

        if not self.indented:
            # block quote
            if c == '>':
                self.advance_next_nonspace()
                self.advance_offset(1, False)
                if _is_space_or_tab(_peek(line, self.offset)):
                    self.advance_offset(1, True)
                self.close_unmatched_blocks()
                self.add_child('block_quote', self.next_nonspace)
                return 1

            # ATX heading
            m = RE_ATX_HEADING_MARKER.match(line, nn)
            if m:
                self.advance_next_nonspace()
                self.advance_offset(m.end() - m.start(), False)
                self.close_unmatched_blocks()
                heading = self.add_child('heading', self.next_nonspace)
                heading.level = len(m.group(0).strip())
                text = line[self.offset:]
                text = re.sub(r'^[ \t]*#+[ \t]*$', '', text)
                text = re.sub(r'[ \t]+#+[ \t]*$', '', text)
                heading.string_content = text
                self.advance_offset(len(line) - self.offset)
                return 2

            # fenced code
            m = RE_CODE_FENCE.match(line, nn)
            if m:
                fence_length = m.end() - m.start()
                self.close_unmatched_blocks()
                block = self.add_child('code_block', self.next_nonspace)
                block.is_fenced = True
                block.fence_length = fence_length
                block.fence_char = m.group(0)[0]
                block.fence_offset = self.indent
                self.advance_next_nonspace()
                self.advance_offset(fence_length, False)
                return 2

            # HTML block
            if c == '<':
                s = line[nn:]
                for block_type in range(1, 8):
                    if RE_HTML_BLOCK_OPEN[block_type].match(s) and (
                            block_type < 7 or (
                                container.type != 'paragraph' and
                                not (not self.all_closed and not self.blank and
                                     self.tip.type == 'paragraph'))):
                        self.close_unmatched_blocks()
                        b = self.add_child('html_block', self.offset)
                        b.html_block_type = block_type
                        return 2

            # setext heading
            if container.type == 'paragraph':
                m = RE_SETEXT_HEADING_LINE.match(line, nn)
                if m:
                    self.close_unmatched_blocks()
                    content, _ = _parse_references(container.string_content, self.refmap)
                    container.string_content = content
                    if content:
                        heading = Node('heading', container.start_line, container.start_col)
                        heading.level = 1 if m.group(0)[0] == '=' else 2
                        heading.string_content = content
                        container.insert_after(heading)
                        container.unlink()
                        self.tip = heading
                        self.advance_offset(len(line) - self.offset, False)
                        return 2

            # thematic break
            if RE_THEMATIC_BREAK.match(line, nn):
                self.close_unmatched_blocks()
                self.add_child('thematic_break', self.next_nonspace)
                self.advance_offset(len(line) - self.offset, False)
                return 2

        # list item
        if not self.indented or container.type == 'list':
            data = self._parse_list_marker(container)
            if data is not None:
                self.close_unmatched_blocks()
                if self.tip.type != 'list' or not _lists_match(container.list_data, data):
                    lst = self.add_child('list', self.next_nonspace)
                    lst.list_data = data
                item = self.add_child('item', self.next_nonspace)
                item.list_data = data
                return 1

        # indented code
        if self.indented and self.tip.type != 'paragraph' and not self.blank:
            self.advance_offset(CODE_INDENT, True)
            self.close_unmatched_blocks()
            self.add_child('code_block', self.offset)
            return 2

        return 0

    # -- line incorporation ------------------------------------------------

    def incorporate_line(self, ln):
        all_matched = True
        container = self.doc
        self.oldtip = self.tip
        self.offset = 0
        self.column = 0
        self.blank = False
        self.partially_consumed_tab = False
        self.line_number += 1
        self.current_line = ln

        while True:
            last_child = container.last_child
            if last_child is None or not last_child.open:
                break
            container = last_child
            self.find_next_nonspace()
            r = self._continue(container)
            if r == 0:
                pass
            elif r == 1:
                all_matched = False
            else:  # r == 2
                self.last_line_length = len(ln)
                return
            if not all_matched:
                container = container.parent
                break

        self.all_closed = container is self.oldtip
        self.last_matched_container = container

        matched_leaf = container.type != 'paragraph' and _accepts_lines(container.type)

        while not matched_leaf:
            self.find_next_nonspace()
            if not self.indented and not RE_MAYBE_SPECIAL.match(ln, self.next_nonspace):
                self.advance_next_nonspace()
                break
            res = self._try_block_starts(container)
            if res == 1:
                container = self.tip
            elif res == 2:
                container = self.tip
                matched_leaf = True
            else:
                self.advance_next_nonspace()
                break

        if not self.all_closed and not self.blank and self.tip.type == 'paragraph':
            # lazy paragraph continuation
            self.add_line()
        else:
            self.close_unmatched_blocks()
            t = container.type
            if _accepts_lines(t):
                self.add_line()
                if t == 'html_block' and 1 <= container.html_block_type <= 5 and \
                        RE_HTML_BLOCK_CLOSE[container.html_block_type].search(ln, self.offset):
                    self.last_line_length = len(ln)
                    self.finalize(container, self.line_number)
            elif self.offset < len(ln) and not self.blank:
                self.add_child('paragraph', self.offset)
                self.advance_next_nonspace()
                self.add_line()
        self.last_line_length = len(ln)

    def parse(self, text):
        text = text.replace('\0', '�')
        lines = RE_LINE_ENDING.split(text)
        n = len(lines)
        if text.endswith('\n'):
            n -= 1
        for i in range(n):
            self.incorporate_line(lines[i])
        while self.tip is not None:
            self.finalize(self.tip, n)
        self._prepare_inline_content(self.doc)
        return self.doc, self.refmap

    def _prepare_inline_content(self, root):
        stack = [root]
        while stack:
            node = stack.pop()
            for child in node.children:
                if child.type in ('paragraph', 'heading'):
                    child.content = child.string_content.strip(' \t\n')
                    child.string_content = ''
                elif child.children:
                    stack.append(child)


def _lists_match(a, b):
    if a is None or b is None:
        return False
    return (a['type'] == b['type'] and a['delimiter'] == b['delimiter']
            and a['bullet_char'] == b['bullet_char'])


def parse(markdown):
    """Parse markdown into a block tree. Returns (doc, refmap)."""
    return BlockParser().parse(markdown)
