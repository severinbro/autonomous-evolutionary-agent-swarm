"""Block-structure parsing for CommonMark 0.31.2.

Builds the container/leaf block tree (block quotes, lists, list items,
paragraphs, headings, thematic breaks, code blocks, HTML blocks), collects
link reference definitions and then runs the inline parser over every
paragraph and heading.
"""

import re

from .node import Node
from .inlines import InlineParser, unescape_string, OPENTAG, CLOSETAG

CODE_INDENT = 4

reLineEnding = re.compile(r'\r\n|\n|\r')
reMaybeSpecial = re.compile(r'[#`~*+_=<>0-9-]')
reNonSpace = re.compile(r'[^ \t\f\v\r\n]')
reBulletListMarker = re.compile(r'[*+-]')
reOrderedListMarker = re.compile(r'(\d{1,9})([.)])')
reATXHeadingMarker = re.compile(r'#{1,6}(?:[ \t]+|$)')
reCodeFence = re.compile(r'`{3,}(?!.*`)|~{3,}')
reClosingCodeFence = re.compile(r'(?:`{3,}|~{3,})(?=[ \t]*$)')
reSetextHeadingLine = re.compile(r'(?:=+|-+)[ \t]*$')
reThematicBreak = re.compile(r'(?:(?:\*[ \t]*){3,}|(?:_[ \t]*){3,}|(?:-[ \t]*){3,})$')
reATXTrailingOnly = re.compile(r'^[ \t]*#+[ \t]*$')
reATXTrailing = re.compile(r'[ \t]+#+[ \t]*$')
reTrailingBlankHtml = re.compile(r'(\n *)+$')
reBlankLine = re.compile(r'^[ \t]*$')
reAllBlank = re.compile(r'^[ \t\r\n]*$')

_BLOCK_TAGS = (
    'address|article|aside|base|basefont|blockquote|body|caption|center|col|'
    'colgroup|dd|details|dialog|dir|div|dl|dt|fieldset|figcaption|figure|'
    'footer|form|frame|frameset|h[123456]|head|header|hr|html|iframe|legend|'
    'li|link|main|menu|menuitem|nav|noframes|ol|optgroup|option|p|param|'
    'search|section|summary|table|tbody|td|tfoot|th|thead|title|tr|track|ul')

reHtmlBlockOpen = [
    None,
    re.compile(r'<(?:script|pre|textarea|style)(?:[ \t\f\v]|>|$)', re.I),
    re.compile(r'<!--'),
    re.compile(r'<[?]'),
    re.compile(r'<![A-Za-z]'),
    re.compile(r'<!\[CDATA\['),
    re.compile(r'</?(?:' + _BLOCK_TAGS + r')(?:[ \t\f\v]|/?>|$)', re.I),
    re.compile(r'(?!</?(?:pre|script|style|textarea)(?![A-Za-z0-9-]))'
               r'(?:' + OPENTAG + '|' + CLOSETAG + r')[ \t\f\v]*$', re.I),
]

reHtmlBlockClose = [
    None,
    re.compile(r'</(?:script|pre|textarea|style)>', re.I),
    re.compile(r'-->'),
    re.compile(r'\?>'),
    re.compile(r'>'),
    re.compile(r'\]\]>'),
]

_CAN_CONTAIN_ANY = frozenset(['document', 'block_quote', 'item'])
_ACCEPTS_LINES = frozenset(['paragraph', 'code_block', 'html_block'])


def _is_space_or_tab(c):
    return c == ' ' or c == '\t'


class ListData:
    __slots__ = ('type', 'tight', 'bullet_char', 'start', 'delimiter',
                 'padding', 'marker_offset')

    def __init__(self, marker_offset):
        self.type = None
        self.tight = True
        self.bullet_char = None
        self.start = None
        self.delimiter = None
        self.padding = None
        self.marker_offset = marker_offset


def _lists_match(a, b):
    return (a.type == b.type and a.delimiter == b.delimiter and
            a.bullet_char == b.bullet_char)


def _ends_with_blank_line(block):
    """True when blank line(s) separate ``block`` from its next sibling."""
    return block.next is not None and block.next.start_line > block.end_line + 1


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

    # ------------------------------------------------------------------
    def parse(self, text):
        self.doc = Node('document')
        self.doc.start_line = 1
        self.tip = self.doc
        self.oldtip = self.doc
        self.refmap = {}
        self.line_number = 0
        self.last_matched_container = self.doc
        self.all_closed = True
        self.current_line = ''
        self.offset = 0
        self.column = 0
        self.next_nonspace = 0
        self.next_nonspace_column = 0
        self.indent = 0
        self.indented = False
        self.blank = False
        self.partially_consumed_tab = False

        lines = reLineEnding.split(text)
        n = len(lines)
        if text.endswith('\n') or text.endswith('\r'):
            n -= 1
        for i in range(n):
            self.incorporate_line(lines[i])
        while self.tip is not None:
            self.finalize(self.tip, n)
        self.process_inlines()
        return self.doc

    def process_inlines(self):
        self.inline_parser.refmap = self.refmap
        targets = [node for node, entering in self.doc.walk()
                   if entering and node.type in ('paragraph', 'heading')]
        for node in targets:
            self.inline_parser.parse(node)

    # -- line position helpers -----------------------------------------
    def peek(self, pos):
        if pos < len(self.current_line):
            return self.current_line[pos]
        return None

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

    def advance_offset(self, count, columns):
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

    # -- tree manipulation -------------------------------------------------
    def add_line(self):
        if self.partially_consumed_tab:
            self.offset += 1
            chars_to_tab = 4 - (self.column % 4)
            self.tip.string_content += ' ' * chars_to_tab
        self.tip.string_content += self.current_line[self.offset:] + '\n'

    def add_child(self, tag, offset):
        while not self._can_contain(self.tip.type, tag):
            self.finalize(self.tip, self.line_number - 1)
        node = Node(tag)
        node.start_line = self.line_number
        self.tip.append_child(node)
        self.tip = node
        return node

    @staticmethod
    def _can_contain(parent_type, child_type):
        if parent_type in _CAN_CONTAIN_ANY:
            return child_type != 'item'
        if parent_type == 'list':
            return child_type == 'item'
        return False

    def close_unmatched_blocks(self):
        if not self.all_closed:
            while self.oldtip is not self.last_matched_container:
                parent = self.oldtip.parent
                self.finalize(self.oldtip, self.line_number - 1)
                self.oldtip = parent
            self.all_closed = True

    # -- continuation ----------------------------------------------------------
    def _continue(self, container):
        t = container.type
        if t == 'document' or t == 'list':
            return 0
        if t == 'block_quote':
            if not self.indented and self.peek(self.next_nonspace) == '>':
                self.advance_next_nonspace()
                self.advance_offset(1, False)
                if _is_space_or_tab(self.peek(self.offset)):
                    self.advance_offset(1, True)
                return 0
            return 1
        if t == 'item':
            data = container.list_data
            if self.blank:
                if container.first_child is None:
                    return 1
                self.advance_next_nonspace()
            elif self.indent >= data.marker_offset + data.padding:
                self.advance_offset(data.marker_offset + data.padding, True)
            else:
                return 1
            return 0
        if t == 'heading' or t == 'thematic_break':
            return 1
        if t == 'code_block':
            if container.is_fenced:
                line = self.current_line
                m = None
                if self.indent <= 3 and self.peek(self.next_nonspace) == container.fence_char:
                    m = reClosingCodeFence.match(line, self.next_nonspace)
                if m is not None and len(m.group(0)) >= container.fence_length:
                    self.finalize(container, self.line_number)
                    return 2
                i = container.fence_offset
                while i > 0 and _is_space_or_tab(self.peek(self.offset)):
                    self.advance_offset(1, True)
                    i -= 1
                return 0
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

    # -- finalization ------------------------------------------------------------
    def finalize(self, block, line_number):
        above = block.parent
        block.open = False
        block.end_line = line_number
        t = block.type
        if t == 'paragraph':
            has_refs = False
            while block.string_content.startswith('['):
                pos = self.inline_parser.parse_reference(block.string_content, self.refmap)
                if not pos:
                    break
                block.string_content = block.string_content[pos:]
                has_refs = True
            if has_refs and reAllBlank.match(block.string_content):
                block.unlink()
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
                popped = 0
                while lines and reBlankLine.match(lines[-1]):
                    lines.pop()
                    popped += 1
                block.literal = '\n'.join(lines) + '\n'
                if popped > 1:
                    block.end_line -= popped - 1
            block.string_content = None
        elif t == 'html_block':
            block.literal = reTrailingBlankHtml.sub('', block.string_content)
            block.string_content = None
        elif t == 'item':
            if block.last_child is not None:
                block.end_line = block.last_child.end_line
            else:
                block.end_line = block.start_line
        elif t == 'list':
            if block.last_child is not None:
                block.end_line = block.last_child.end_line
            tight = True
            item = block.first_child
            while item is not None and tight:
                if _ends_with_blank_line(item):
                    tight = False
                    break
                sub = item.first_child
                while sub is not None:
                    if _ends_with_blank_line(sub):
                        tight = False
                        break
                    sub = sub.next
                item = item.next
            block.list_data.tight = tight
        self.tip = above

    # -- block starts ----------------------------------------------------------
    def _start_block_quote(self, container):
        if not self.indented and self.peek(self.next_nonspace) == '>':
            self.advance_next_nonspace()
            self.advance_offset(1, False)
            if _is_space_or_tab(self.peek(self.offset)):
                self.advance_offset(1, True)
            self.close_unmatched_blocks()
            self.add_child('block_quote', self.next_nonspace)
            return 1
        return 0

    def _start_atx_heading(self, container):
        if self.indented:
            return 0
        m = reATXHeadingMarker.match(self.current_line, self.next_nonspace)
        if m is None:
            return 0
        self.advance_next_nonspace()
        self.advance_offset(len(m.group(0)), False)
        self.close_unmatched_blocks()
        heading = self.add_child('heading', self.next_nonspace)
        heading.level = len(m.group(0).strip(' \t'))
        content = self.current_line[self.offset:]
        content = reATXTrailingOnly.sub('', content)
        content = reATXTrailing.sub('', content)
        heading.string_content = content
        self.advance_offset(len(self.current_line) - self.offset, False)
        return 2

    def _start_fenced_code(self, container):
        if self.indented:
            return 0
        m = reCodeFence.match(self.current_line, self.next_nonspace)
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
        if self.indented or self.peek(self.next_nonspace) != '<':
            return 0
        s = self.current_line[self.next_nonspace:]
        for block_type in range(1, 8):
            if reHtmlBlockOpen[block_type].match(s):
                if block_type == 7 and (
                        container.type == 'paragraph' or
                        (not self.all_closed and not self.blank and
                         self.tip.type == 'paragraph')):
                    continue
                self.close_unmatched_blocks()
                block = self.add_child('html_block', self.offset)
                block.html_block_type = block_type
                return 2
        return 0

    def _start_setext_heading(self, container):
        if self.indented or container.type != 'paragraph':
            return 0
        m = reSetextHeadingLine.match(self.current_line, self.next_nonspace)
        if m is None:
            return 0
        self.close_unmatched_blocks()
        while container.string_content.startswith('['):
            pos = self.inline_parser.parse_reference(container.string_content, self.refmap)
            if not pos:
                break
            container.string_content = container.string_content[pos:]
        if len(container.string_content) > 0:
            heading = Node('heading')
            heading.start_line = container.start_line
            heading.level = 1 if m.group(0)[0] == '=' else 2
            heading.string_content = container.string_content
            container.insert_after(heading)
            container.unlink()
            self.tip = heading
            self.advance_offset(len(self.current_line) - self.offset, False)
            return 2
        return 0

    def _start_thematic_break(self, container):
        if self.indented:
            return 0
        if reThematicBreak.match(self.current_line, self.next_nonspace) is None:
            return 0
        self.close_unmatched_blocks()
        self.add_child('thematic_break', self.next_nonspace)
        self.advance_offset(len(self.current_line) - self.offset, False)
        return 2

    def _parse_list_marker(self, container):
        if self.indent >= 4:
            return None
        line = self.current_line
        data = ListData(self.indent)
        m = reBulletListMarker.match(line, self.next_nonspace)
        if m is not None:
            data.type = 'bullet'
            data.bullet_char = m.group(0)[0]
        else:
            m = reOrderedListMarker.match(line, self.next_nonspace)
            if m is not None and (container.type != 'paragraph' or int(m.group(1)) == 1):
                data.type = 'ordered'
                data.start = int(m.group(1))
                data.delimiter = m.group(2)
            else:
                return None
        marker_len = len(m.group(0))
        nextc = self.peek(self.next_nonspace + marker_len)
        if not (nextc is None or nextc == '\t' or nextc == ' '):
            return None
        if (container.type == 'paragraph' and
                not reNonSpace.search(line, self.next_nonspace + marker_len)):
            return None
        self.advance_next_nonspace()
        self.advance_offset(marker_len, True)
        spaces_start_col = self.column
        spaces_start_offset = self.offset
        while True:
            self.advance_offset(1, True)
            nextc = self.peek(self.offset)
            if not (self.column - spaces_start_col < 5 and _is_space_or_tab(nextc)):
                break
        blank_item = self.peek(self.offset) is None
        spaces_after_marker = self.column - spaces_start_col
        if spaces_after_marker >= 5 or spaces_after_marker < 1 or blank_item:
            data.padding = marker_len + 1
            self.column = spaces_start_col
            self.offset = spaces_start_offset
            self.partially_consumed_tab = False
            if _is_space_or_tab(self.peek(self.offset)):
                self.advance_offset(1, True)
        else:
            data.padding = marker_len + spaces_after_marker
        return data

    def _start_list_item(self, container):
        if self.indented and container.type != 'list':
            return 0
        data = self._parse_list_marker(container)
        if data is None:
            return 0
        self.close_unmatched_blocks()
        if self.tip.type != 'list' or not _lists_match(self.tip.list_data, data):
            lst = self.add_child('list', self.next_nonspace)
            lst.list_data = data
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

    # -- main per-line routine ---------------------------------------------------
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

        matched_leaf = container.type != 'paragraph' and container.type in _ACCEPTS_LINES

        while not matched_leaf:
            self.find_next_nonspace()
            if not self.indented and not reMaybeSpecial.match(ln, self.next_nonspace):
                self.advance_next_nonspace()
                break
            started = False
            for start in self.block_starts:
                res = start(container)
                if res == 1:
                    container = self.tip
                    started = True
                    break
                if res == 2:
                    container = self.tip
                    matched_leaf = True
                    started = True
                    break
            if not started:
                self.advance_next_nonspace()
                break

        if not self.all_closed and not self.blank and self.tip.type == 'paragraph':
            # lazy paragraph continuation
            self.add_line()
        else:
            self.close_unmatched_blocks()
            t = container.type
            if t in _ACCEPTS_LINES:
                self.add_line()
                if (t == 'html_block' and 1 <= container.html_block_type <= 5 and
                        reHtmlBlockClose[container.html_block_type].search(
                            self.current_line, self.offset)):
                    self.finalize(container, self.line_number)
            elif self.offset < len(ln) and not self.blank:
                self.add_child('paragraph', self.offset)
                self.advance_next_nonspace()
                self.add_line()


def parse(text):
    """Parse ``text`` into a document tree with inline content resolved."""
    return BlockParser().parse(text)
