"""Block-structure parsing for CommonMark."""
import re

from .node import Node, ListData
from .inlines import InlineParser
from .common import unescape_string, OPENTAG, CLOSETAG

CODE_INDENT = 4

RE_MAYBE_SPECIAL = re.compile(r'[#`~*+_=<>0-9-]')
RE_NON_SPACE = re.compile(r'[^ \t\f\v\r\n]')
RE_BULLET_LIST_MARKER = re.compile(r'[*+-]')
RE_ORDERED_LIST_MARKER = re.compile(r'(\d{1,9})([.)])')
RE_ATX_HEADING_MARKER = re.compile(r'#{1,6}(?:[ \t]+|$)')
RE_CODE_FENCE = re.compile(r'`{3,}(?!.*`)|~{3,}')
RE_CLOSING_CODE_FENCE = re.compile(r'(?:`{3,}|~{3,})(?=[ \t]*$)')
RE_SETEXT_HEADING_LINE = re.compile(r'(?:=+|-+)[ \t]*$')
RE_LINE_ENDING = re.compile(r'\r\n|\n|\r')
RE_THEMATIC_BREAK = re.compile(
    r'(?:(?:\*[ \t]*){3,}|(?:_[ \t]*){3,}|(?:-[ \t]*){3,})$')
RE_ATX_CLOSING_ONLY = re.compile(r'^[ \t]*#+[ \t]*$')
RE_ATX_CLOSING = re.compile(r'[ \t]+#+[ \t]*$')
RE_TRAILING_BLANK_LINES = re.compile(r'(?:\n[ \t]*)+\Z')

_BLOCK6_TAGS = (
    'address|article|aside|base|basefont|blockquote|body|caption|center|col|'
    'colgroup|dd|details|dialog|dir|div|dl|dt|fieldset|figcaption|figure|'
    'footer|form|frame|frameset|h[123456]|head|header|hr|html|iframe|legend|'
    'li|link|main|menu|menuitem|nav|noframes|ol|optgroup|option|p|param|'
    'search|section|summary|table|tbody|td|tfoot|th|thead|title|tr|track|ul')

RE_HTML_BLOCK_OPEN = [
    None,
    re.compile(r'<(?:script|pre|textarea|style)(?:[ \t\n\r\f\v]|>|$)', re.I),
    re.compile(r'<!--'),
    re.compile(r'<\?'),
    re.compile(r'<![A-Za-z]'),
    re.compile(r'<!\[CDATA\['),
    re.compile(r'</?(?:' + _BLOCK6_TAGS + r')(?:[ \t\n\r\f\v]|/?>|$)', re.I),
    re.compile(r'(?:' + OPENTAG + '|' + CLOSETAG + r')[ \t\n\r\f\v]*$', re.I),
]

RE_HTML_BLOCK_CLOSE = [
    None,
    re.compile(r'</(?:script|pre|textarea|style)>', re.I),
    re.compile(r'-->'),
    re.compile(r'\?>'),
    re.compile(r'>'),
    re.compile(r'\]\]>'),
]

ACCEPTS_LINES = {
    'document': False, 'list': False, 'block_quote': False, 'item': False,
    'heading': False, 'thematic_break': False, 'code_block': True,
    'html_block': True, 'paragraph': True,
}


def can_contain(parent_type, child_type):
    if parent_type == 'document' or parent_type == 'block_quote':
        return child_type != 'item'
    if parent_type == 'item':
        return child_type != 'item'
    if parent_type == 'list':
        return child_type == 'item'
    return False


def peek(s, pos):
    return s[pos] if 0 <= pos < len(s) else ''


def is_space_or_tab(c):
    return c == ' ' or c == '\t'


def lists_match(a, b):
    return (a.type == b.type and a.delimiter == b.delimiter
            and a.bullet_char == b.bullet_char)


def ends_with_blank_line(node):
    cur = node
    while cur is not None:
        if cur.last_line_blank:
            return True
        if cur.type in ('list', 'item'):
            cur = cur.last_child
        else:
            cur = None
    return False


class BlockParser:
    def __init__(self):
        self.inline_parser = InlineParser()
        self.block_starts = [
            self._start_block_quote,
            self._start_atx_heading,
            self._start_fenced_code,
            self._start_html_block,
            self._start_setext_heading,
            self._start_thematic_break,
            self._start_list_item,
            self._start_indented_code,
        ]

    # -- public ---------------------------------------------------------
    def parse(self, text):
        self.doc = Node('document')
        self.doc.start_line = 1
        self.tip = self.doc
        self.oldtip = self.doc
        self.refmap = {}
        self.line_number = 0
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
        lines = RE_LINE_ENDING.split(text)
        n = len(lines)
        if text and text[-1] in '\r\n':
            n -= 1
        for i in range(n):
            self.incorporate_line(lines[i])
        while self.tip is not None:
            self.finalize(self.tip, n)
        self.process_inlines()
        return self.doc

    # -- line position helpers --------------------------------------------
    def find_next_nonspace(self):
        ln = self.current_line
        i = self.offset
        cols = self.column
        n = len(ln)
        c = ''
        while i < n:
            c = ln[i]
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

    def advance_offset(self, count, columns):
        ln = self.current_line
        n = len(ln)
        while count > 0 and self.offset < n:
            c = ln[self.offset]
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

    # -- tree helpers ---------------------------------------------------
    def add_line(self):
        if self.partially_consumed_tab:
            self.offset += 1
            chars_to_tab = 4 - (self.column % 4)
            self.tip.string_content += ' ' * chars_to_tab
        self.tip.string_content += self.current_line[self.offset:] + '\n'

    def add_child(self, tag, offset):
        while not can_contain(self.tip.type, tag):
            self.finalize(self.tip, self.line_number - 1)
        node = Node(tag)
        node.start_line = self.line_number
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

    # -- continuation -----------------------------------------------------
    def _continue(self, container):
        t = container.type
        ln = self.current_line
        if t == 'document' or t == 'list':
            return 0
        if t == 'block_quote':
            if not self.indented and peek(ln, self.next_nonspace) == '>':
                self.advance_next_nonspace()
                self.advance_offset(1, False)
                if is_space_or_tab(peek(ln, self.offset)):
                    self.advance_offset(1, True)
                return 0
            return 1
        if t == 'item':
            ld = container.list_data
            if self.blank:
                if container.first_child is None:
                    return 1
                self.advance_next_nonspace()
            elif self.indent >= ld.marker_offset + ld.padding:
                self.advance_offset(ld.marker_offset + ld.padding, True)
            else:
                return 1
            return 0
        if t == 'heading' or t == 'thematic_break':
            return 1
        if t == 'code_block':
            if container.is_fenced:
                m = None
                if (self.indent <= 3 and
                        peek(ln, self.next_nonspace) == container.fence_char):
                    m = RE_CLOSING_CODE_FENCE.match(ln, self.next_nonspace)
                if m is not None and len(m.group(0)) >= container.fence_length:
                    self.finalize(container, self.line_number)
                    return 2
                i = container.fence_offset
                while i > 0 and is_space_or_tab(peek(ln, self.offset)):
                    self.advance_offset(1, True)
                    i -= 1
            else:
                if self.indent >= CODE_INDENT:
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
        return 1

    # -- finalization -----------------------------------------------------
    def finalize(self, block, line_number):
        above = block.parent
        block.open = False
        t = block.type
        if t == 'paragraph':
            self._finalize_paragraph(block)
        elif t == 'code_block':
            content = block.string_content
            if block.is_fenced:
                nl = content.find('\n')
                first_line = content[:nl]
                rest = content[nl + 1:]
                block.info = unescape_string(first_line.strip(' \t'))
                block.literal = rest
            else:
                lines = content.split('\n')
                while lines and lines[-1].strip(' \t') == '':
                    lines.pop()
                block.literal = '\n'.join(lines) + '\n' if lines else ''
            block.string_content = None
        elif t == 'html_block':
            block.literal = RE_TRAILING_BLANK_LINES.sub('', block.string_content)
            block.string_content = None
        elif t == 'list':
            self._finalize_list(block)
        self.tip = above

    def _finalize_paragraph(self, block):
        has_refs = False
        content = block.string_content
        while content.startswith('['):
            pos = self.inline_parser.parse_reference(content, self.refmap)
            if not pos:
                break
            content = content[pos:]
            has_refs = True
        block.string_content = content
        if has_refs and content.strip(' \t\r\n\f\v') == '':
            block.unlink()

    def _finalize_list(self, block):
        tight = True
        item = block.first_child
        while item is not None:
            if item.last_line_blank and item.next is not None:
                tight = False
                break
            sub = item.first_child
            while sub is not None:
                if ((item.next is not None or sub.next is not None)
                        and ends_with_blank_line(sub)):
                    tight = False
                    break
                sub = sub.next
            if not tight:
                break
            item = item.next
        block.list_data.tight = tight

    # -- block starts -----------------------------------------------------
    def _start_block_quote(self, container):
        ln = self.current_line
        if not self.indented and peek(ln, self.next_nonspace) == '>':
            self.advance_next_nonspace()
            self.advance_offset(1, False)
            if is_space_or_tab(peek(ln, self.offset)):
                self.advance_offset(1, True)
            self.close_unmatched_blocks()
            self.add_child('block_quote', self.next_nonspace)
            return 1
        return 0

    def _start_atx_heading(self, container):
        if self.indented:
            return 0
        ln = self.current_line
        m = RE_ATX_HEADING_MARKER.match(ln, self.next_nonspace)
        if m is None:
            return 0
        self.advance_next_nonspace()
        self.advance_offset(len(m.group(0)), False)
        self.close_unmatched_blocks()
        heading = self.add_child('heading', self.next_nonspace)
        heading.level = len(m.group(0).strip(' \t'))
        rest = ln[self.offset:]
        rest = RE_ATX_CLOSING_ONLY.sub('', rest)
        rest = RE_ATX_CLOSING.sub('', rest)
        heading.string_content = rest
        self.advance_offset(len(ln) - self.offset, False)
        return 2

    def _start_fenced_code(self, container):
        if self.indented:
            return 0
        ln = self.current_line
        m = RE_CODE_FENCE.match(ln, self.next_nonspace)
        if m is None:
            return 0
        fence_length = len(m.group(0))
        self.close_unmatched_blocks()
        block = self.add_child('code_block', self.next_nonspace)
        block.is_fenced = True
        block.fence_length = fence_length
        block.fence_char = m.group(0)[0]
        block.fence_offset = self.indent
        self.advance_next_nonspace()
        self.advance_offset(fence_length, False)
        return 2

    def _start_html_block(self, container):
        ln = self.current_line
        if self.indented or peek(ln, self.next_nonspace) != '<':
            return 0
        s = ln[self.next_nonspace:]
        for block_type in range(1, 8):
            if RE_HTML_BLOCK_OPEN[block_type].match(s):
                if block_type == 7:
                    if container.type == 'paragraph':
                        continue
                    if (not self.all_closed and not self.blank
                            and self.tip.type == 'paragraph'):
                        continue
                self.close_unmatched_blocks()
                b = self.add_child('html_block', self.offset)
                b.html_block_type = block_type
                return 2
        return 0

    def _start_setext_heading(self, container):
        if self.indented or container.type != 'paragraph':
            return 0
        ln = self.current_line
        m = RE_SETEXT_HEADING_LINE.match(ln, self.next_nonspace)
        if m is None:
            return 0
        self.close_unmatched_blocks()
        content = container.string_content
        while content.startswith('['):
            pos = self.inline_parser.parse_reference(content, self.refmap)
            if not pos:
                break
            content = content[pos:]
        container.string_content = content
        if content:
            heading = Node('heading')
            heading.start_line = container.start_line
            heading.level = 1 if m.group(0)[0] == '=' else 2
            heading.string_content = content
            container.insert_after(heading)
            container.unlink()
            self.tip = heading
            self.advance_offset(len(ln) - self.offset, False)
            return 2
        return 0

    def _start_thematic_break(self, container):
        if self.indented:
            return 0
        ln = self.current_line
        if RE_THEMATIC_BREAK.match(ln, self.next_nonspace):
            self.close_unmatched_blocks()
            self.add_child('thematic_break', self.next_nonspace)
            self.advance_offset(len(ln) - self.offset, False)
            return 2
        return 0

    def _parse_list_marker(self, container):
        ln = self.current_line
        if self.indent >= 4:
            return None
        data = ListData()
        data.marker_offset = self.indent
        m = RE_BULLET_LIST_MARKER.match(ln, self.next_nonspace)
        if m is not None:
            data.type = 'bullet'
            data.bullet_char = m.group(0)
        else:
            m = RE_ORDERED_LIST_MARKER.match(ln, self.next_nonspace)
            if m is not None and (container.type != 'paragraph'
                                  or int(m.group(1)) == 1):
                data.type = 'ordered'
                data.start = int(m.group(1))
                data.delimiter = m.group(2)
            else:
                return None
        mlen = len(m.group(0))
        nextc = peek(ln, self.next_nonspace + mlen)
        if not (nextc == '' or nextc == '\t' or nextc == ' '):
            return None
        if (container.type == 'paragraph'
                and not RE_NON_SPACE.search(ln, self.next_nonspace + mlen)):
            return None
        self.advance_next_nonspace()
        self.advance_offset(mlen, True)
        spaces_start_col = self.column
        spaces_start_offset = self.offset
        while True:
            self.advance_offset(1, True)
            nextc = peek(ln, self.offset)
            if not (self.column - spaces_start_col < 5 and is_space_or_tab(nextc)):
                break
        blank_item = peek(ln, self.offset) == ''
        spaces_after_marker = self.column - spaces_start_col
        if spaces_after_marker >= 5 or spaces_after_marker < 1 or blank_item:
            data.padding = mlen + 1
            self.column = spaces_start_col
            self.offset = spaces_start_offset
            if is_space_or_tab(peek(ln, self.offset)):
                self.advance_offset(1, True)
        else:
            data.padding = mlen + spaces_after_marker
        return data

    def _start_list_item(self, container):
        if self.indented and container.type != 'list':
            return 0
        data = self._parse_list_marker(container)
        if data is None:
            return 0
        self.close_unmatched_blocks()
        if self.tip.type != 'list' or not lists_match(container.list_data, data):
            container = self.add_child('list', self.next_nonspace)
            container.list_data = data
        item = self.add_child('item', self.next_nonspace)
        item.list_data = data
        return 1

    def _start_indented_code(self, container):
        if self.indented and self.tip.type != 'paragraph' and not self.blank:
            self.advance_offset(CODE_INDENT, True)
            self.close_unmatched_blocks()
            self.add_child('code_block', self.offset)
            return 2
        return 0

    # -- main line processing -------------------------------------------
    def incorporate_line(self, ln):
        all_matched = True
        container = self.doc
        self.oldtip = self.tip
        self.offset = 0
        self.column = 0
        self.blank = False
        self.partially_consumed_tab = False
        self.line_number += 1
        if '\x00' in ln:
            ln = ln.replace('\x00', '�')
        self.current_line = ln

        while True:
            last_child = container.last_child
            if last_child is None or not last_child.open:
                break
            container = last_child
            self.find_next_nonspace()
            res = self._continue(container)
            if res == 0:
                continue
            if res == 1:
                all_matched = False
                container = container.parent
                break
            return  # res == 2: closing code fence consumed the line

        self.all_closed = container is self.oldtip
        self.last_matched_container = container

        matched_leaf = (container.type != 'paragraph'
                        and ACCEPTS_LINES[container.type])
        starts = self.block_starts
        while not matched_leaf:
            self.find_next_nonspace()
            if (not self.indented and
                    not RE_MAYBE_SPECIAL.match(ln, self.next_nonspace)):
                self.advance_next_nonspace()
                break
            res = 0
            for start in starts:
                res = start(container)
                if res:
                    break
            if res == 1:
                container = self.tip
            elif res == 2:
                container = self.tip
                matched_leaf = True
            else:
                self.advance_next_nonspace()
                break

        # Track blank-line information used for list tightness.
        if self.blank and container.last_child is not None:
            container.last_child.last_line_blank = True
        t = container.type
        last_line_blank = self.blank and not (
            t == 'block_quote' or t == 'heading' or t == 'thematic_break'
            or (t == 'code_block' and container.is_fenced)
            or (t == 'item' and container.first_child is None
                and container.start_line == self.line_number))
        container.last_line_blank = last_line_blank
        p = container.parent
        while p is not None:
            p.last_line_blank = False
            p = p.parent

        if (not self.all_closed and not self.blank
                and self.tip.type == 'paragraph'):
            # lazy paragraph continuation
            self.add_line()
        else:
            self.close_unmatched_blocks()
            t = container.type
            if ACCEPTS_LINES[t]:
                self.add_line()
                if (t == 'html_block' and 1 <= container.html_block_type <= 5
                        and RE_HTML_BLOCK_CLOSE[container.html_block_type]
                        .search(ln, self.offset)):
                    self.finalize(container, self.line_number)
            elif self.offset < len(ln) and not self.blank:
                self.add_child('paragraph', self.offset)
                self.advance_next_nonspace()
                self.add_line()

    # -- inline processing ------------------------------------------------
    def process_inlines(self):
        targets = [node for node, entering in self.doc.walk()
                   if entering and node.type in ('paragraph', 'heading')]
        for node in targets:
            self.inline_parser.parse(node, self.refmap)
