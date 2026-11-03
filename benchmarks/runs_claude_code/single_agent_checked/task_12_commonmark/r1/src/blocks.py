"""Block-structure parsing for CommonMark 0.31.2.

Builds the tree of container blocks (document, block quotes, lists, list
items) and leaf blocks (paragraphs, headings, thematic breaks, code blocks,
HTML blocks), collects link reference definitions, and finally runs the
inline parser over paragraph and heading content.
"""

import re

from .inlines import CLOSETAG, OPENTAG, InlineParser, unescape_string
from .node import ListData, Node

CODE_INDENT = 4

RE_MAYBE_SPECIAL = re.compile(r'[#`~*+_=<>0-9-]')
RE_NON_SPACE = re.compile(r'[^ \t\f\v\r\n]')
RE_BULLET = re.compile(r'[*+-]')
RE_ORDERED = re.compile(r'(\d{1,9})([.)])')
RE_ATX = re.compile(r'#{1,6}(?:[ \t]+|$)')
RE_ATX_EMPTY_CLOSE = re.compile(r'^[ \t]*#+[ \t]*$')
RE_ATX_CLOSE = re.compile(r'[ \t]+#+[ \t]*$')
RE_CODE_FENCE = re.compile(r'`{3,}(?!.*`)|~{3,}')
RE_CLOSING_FENCE = re.compile(r'(?:`{3,}|~{3,})(?=[ \t]*$)')
RE_SETEXT = re.compile(r'(?:=+|-+)[ \t]*$')
RE_THEMATIC = re.compile(r'(?:\*[ \t]*){3,}$|(?:_[ \t]*){3,}$|(?:-[ \t]*){3,}$')
RE_BLANK_LINE = re.compile(r'[ \t]*')
RE_HTML_TRAILING = re.compile(r'(?:\n *)+\Z')

BLOCK_TAGS = (
    'address|article|aside|base|basefont|blockquote|body|caption|center|col|'
    'colgroup|dd|details|dialog|dir|div|dl|dt|fieldset|figcaption|figure|'
    'footer|form|frame|frameset|h[123456]|head|header|hr|html|iframe|legend|'
    'li|link|main|menu|menuitem|nav|noframes|ol|optgroup|option|p|param|'
    'search|section|summary|table|tbody|td|tfoot|th|thead|title|tr|track|ul')

RE_HTML_BLOCK_OPEN = [
    None,
    re.compile(r'<(?:script|pre|textarea|style)(?:[ \t]|>|$)', re.I),
    re.compile(r'<!--'),
    re.compile(r'<\?'),
    re.compile(r'<![A-Za-z]'),
    re.compile(r'<!\[CDATA\['),
    re.compile(r'</?(?:' + BLOCK_TAGS + r')(?:[ \t]|/?>|$)', re.I),
    re.compile(r'(?:' + OPENTAG + '|' + CLOSETAG + r')[ \t]*$'),
]
RE_HTML_BLOCK_CLOSE = [
    None,
    re.compile(r'</(?:script|pre|textarea|style)>', re.I),
    re.compile(r'-->'),
    re.compile(r'\?>'),
    re.compile(r'>'),
    re.compile(r'\]\]>'),
]
RE_TYPE7_EXCLUDED = re.compile(r'</?(?:script|style|pre|textarea)(?![A-Za-z0-9-])', re.I)

ACCEPTS_LINES = frozenset(['paragraph', 'code_block', 'html_block'])


def _is_space_or_tab(c):
    return c == ' ' or c == '\t'


def _peek(line, pos):
    if 0 <= pos < len(line):
        return line[pos]
    return ''


def _can_contain(parent_type, child_type):
    if parent_type in ('document', 'block_quote', 'item'):
        return child_type != 'item'
    if parent_type == 'list':
        return child_type == 'item'
    return False


def _is_blank(s):
    return RE_NON_SPACE.search(s) is None


def _ends_with_blank_line(block):
    """True if a blank line separates block from its next sibling."""
    nxt = block.next
    return nxt is not None and block.end_line < nxt.start_line - 1


def _lists_match(a, b):
    return (a.type == b.type and a.delimiter == b.delimiter
            and a.bullet_char == b.bullet_char)


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
    # Public API
    # ------------------------------------------------------------------
    def parse(self, source):
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

        source = source.replace('\0', '�')
        lines = re.split(r'\r\n|\n|\r', source)
        count = len(lines)
        if source.endswith('\n') or source.endswith('\r'):
            count -= 1
        for i in range(count):
            self.incorporate_line(lines[i])
        while self.tip is not None:
            self.finalize(self.tip, count)
        self.process_inlines(self.doc)
        return self.doc

    # ------------------------------------------------------------------
    # Position helpers
    # ------------------------------------------------------------------
    def find_next_nonspace(self):
        line = self.current_line
        i = self.offset
        if self._line_has_no_tabs and self._nn_start <= i <= self._nn_end:
            # Still inside the whitespace run scanned before (tab-free line):
            # reuse the result instead of rescanning (keeps deep nesting fast).
            end = self._nn_end
            self.blank = self._nn_blank
            self.next_nonspace = end
            self.next_nonspace_column = self.column + (end - i)
            self.indent = end - i
            self.indented = self.indent >= CODE_INDENT
            return
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
        self._nn_start = self.offset
        self._nn_end = i
        self._nn_blank = self.blank
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
                    adv = count if chars_to_tab > count else chars_to_tab
                    self.column += adv
                    if not self.partially_consumed_tab:
                        self.offset += 1
                    count -= adv
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
        tip = self.tip
        parts = tip.string_parts
        if parts is None:
            parts = tip.string_parts = []
        if self.partially_consumed_tab:
            self.offset += 1
            chars_to_tab = 4 - (self.column % 4)
            parts.append(' ' * chars_to_tab)
        parts.append(self.current_line[self.offset:] + '\n')

    def add_child(self, node_type, offset):
        while not _can_contain(self.tip.type, node_type):
            self.finalize(self.tip, self.line_number - 1)
        node = Node(node_type)
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

    # ------------------------------------------------------------------
    # Line processing
    # ------------------------------------------------------------------
    def incorporate_line(self, line):
        all_matched = True
        container = self.doc
        self.oldtip = self.tip
        self.offset = 0
        self.column = 0
        self.blank = False
        self.partially_consumed_tab = False
        self.line_number += 1
        self.current_line = line
        self._line_has_no_tabs = '\t' not in line
        self._nn_start = -1
        self._nn_end = -2
        self._nn_blank = False

        # 1. Try to match the line against each open container.
        while True:
            last_child = container.last_child
            if last_child is None or not last_child.open:
                break
            container = last_child
            self.find_next_nonspace()
            res = self.continue_block(container)
            if res == 0:
                continue
            if res == 1:
                all_matched = False
                break
            # res == 2: line fully consumed (closing code fence)
            return
        if not all_matched:
            container = container.parent

        self.all_closed = container is self.oldtip
        self.last_matched_container = container

        # 2. Look for new block starts.
        matched_leaf = (container.type != 'paragraph'
                        and container.type in ACCEPTS_LINES)
        starts = self.block_starts
        while not matched_leaf:
            self.find_next_nonspace()
            if (not self.indented
                    and not RE_MAYBE_SPECIAL.match(line, self.next_nonspace)):
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

        # 3. Add the remaining text to the appropriate block.
        if (not self.all_closed and not self.blank
                and self.tip.type == 'paragraph'):
            # lazy paragraph continuation
            self.add_line()
            return

        self.close_unmatched_blocks()
        t = container.type
        if t in ACCEPTS_LINES:
            self.add_line()
            if (t == 'html_block' and 1 <= container.html_block_type <= 5
                    and RE_HTML_BLOCK_CLOSE[container.html_block_type].search(
                        line[self.offset:])):
                self.finalize(container, self.line_number)
        elif self.offset < len(line) and not self.blank:
            self.add_child('paragraph', self.offset)
            self.advance_next_nonspace()
            self.add_line()

    def continue_block(self, container):
        """0 = matched, 1 = not matched, 2 = line consumed (fence closed)."""
        t = container.type
        line = self.current_line
        if t == 'document' or t == 'list':
            return 0
        if t == 'block_quote':
            if not self.indented and _peek(line, self.next_nonspace) == '>':
                self.advance_next_nonspace()
                self.advance_offset(1, False)
                if _is_space_or_tab(_peek(line, self.offset)):
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
                m = None
                if (self.indent <= 3
                        and _peek(line, self.next_nonspace) == container.fence_char):
                    m = RE_CLOSING_FENCE.match(line, self.next_nonspace)
                if m is not None and len(m.group(0)) >= container.fence_length:
                    self.finalize(container, self.line_number)
                    return 2
                i = container.fence_offset
                while i > 0 and _is_space_or_tab(_peek(line, self.offset)):
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
        return 0

    # ------------------------------------------------------------------
    # Block starts: 0 = no match, 1 = container start, 2 = leaf start
    # ------------------------------------------------------------------
    def _start_block_quote(self, container):
        line = self.current_line
        if not self.indented and _peek(line, self.next_nonspace) == '>':
            self.advance_next_nonspace()
            self.advance_offset(1, False)
            if _is_space_or_tab(_peek(line, self.offset)):
                self.advance_offset(1, True)
            self.close_unmatched_blocks()
            self.add_child('block_quote', self.next_nonspace)
            return 1
        return 0

    def _start_atx_heading(self, container):
        if self.indented:
            return 0
        m = RE_ATX.match(self.current_line, self.next_nonspace)
        if m is None:
            return 0
        self.advance_next_nonspace()
        self.advance_offset(len(m.group(0)), False)
        self.close_unmatched_blocks()
        heading = self.add_child('heading', self.next_nonspace)
        heading.level = len(m.group(0).strip(' \t'))
        content = self.current_line[self.offset:]
        content = RE_ATX_EMPTY_CLOSE.sub('', content)
        content = RE_ATX_CLOSE.sub('', content)
        heading.string_content = content
        self.advance_offset(len(self.current_line) - self.offset, False)
        return 2

    def _start_fenced_code(self, container):
        if self.indented:
            return 0
        m = RE_CODE_FENCE.match(self.current_line, self.next_nonspace)
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
        line = self.current_line
        if self.indented or _peek(line, self.next_nonspace) != '<':
            return 0
        s = line[self.next_nonspace:]
        for block_type in range(1, 8):
            if not RE_HTML_BLOCK_OPEN[block_type].match(s):
                continue
            if block_type == 7:
                if container.type == 'paragraph':
                    continue
                if (not self.all_closed and not self.blank
                        and self.tip.type == 'paragraph'):
                    continue
                if RE_TYPE7_EXCLUDED.match(s):
                    continue
            self.close_unmatched_blocks()
            block = self.add_child('html_block', self.offset)
            block.html_block_type = block_type
            return 2
        return 0

    def _start_setext_heading(self, container):
        if self.indented or container.type != 'paragraph':
            return 0
        m = RE_SETEXT.match(self.current_line, self.next_nonspace)
        if m is None:
            return 0
        self.close_unmatched_blocks()
        content = self._strip_reference_definitions(container.content())
        container.string_content = content
        if _is_blank(content):
            return 0
        heading = Node('heading')
        heading.start_line = container.start_line
        heading.level = 1 if m.group(0)[0] == '=' else 2
        heading.string_content = content
        container.insert_after(heading)
        container.unlink()
        self.tip = heading
        self.advance_offset(len(self.current_line) - self.offset, False)
        return 2

    def _start_thematic_break(self, container):
        if self.indented:
            return 0
        if not RE_THEMATIC.match(self.current_line, self.next_nonspace):
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
        m = RE_BULLET.match(line, self.next_nonspace)
        if m is not None:
            data.type = 'bullet'
            data.bullet_char = m.group(0)[0]
        else:
            m = RE_ORDERED.match(line, self.next_nonspace)
            if m is not None and (container.type != 'paragraph' or m.group(1) == '1'):
                data.type = 'ordered'
                data.start = int(m.group(1))
                data.delimiter = m.group(2)
            else:
                return None
        marker_len = len(m.group(0))
        nextc = _peek(line, self.next_nonspace + marker_len)
        if not (nextc == '' or nextc == '\t' or nextc == ' '):
            return None
        if (container.type == 'paragraph'
                and not RE_NON_SPACE.search(line, self.next_nonspace + marker_len)):
            return None

        self.advance_next_nonspace()
        self.advance_offset(marker_len, True)
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
            data.padding = marker_len + 1
            self.column = spaces_start_col
            self.offset = spaces_start_offset
            self.partially_consumed_tab = False
            if _is_space_or_tab(_peek(line, self.offset)):
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
            lst.list_data = data.copy()
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

    # ------------------------------------------------------------------
    # Finalization
    # ------------------------------------------------------------------
    def finalize(self, block, line_number):
        above = block.parent
        block.open = False
        block.end_line = line_number
        t = block.type
        if t == 'paragraph':
            self._finalize_paragraph(block)
        elif t == 'code_block':
            self._finalize_code_block(block)
        elif t == 'html_block':
            block.literal = RE_HTML_TRAILING.sub('', block.content())
            block.string_content = ''
        elif t == 'list':
            self._finalize_list(block)
        elif t == 'item':
            if block.last_child is not None:
                block.end_line = block.last_child.end_line
            else:
                block.end_line = block.start_line
        self.tip = above

    def _strip_reference_definitions(self, content):
        """Remove leading link reference definitions, recording them."""
        pos = 0
        while content.startswith('[', pos):
            consumed = self.inline_parser.parse_reference(content, self.refmap, pos)
            if not consumed:
                break
            pos += consumed
        return content[pos:] if pos else content

    def _finalize_paragraph(self, block):
        content = self._strip_reference_definitions(block.content())
        block.string_content = content
        if _is_blank(content):
            block.unlink()

    def _finalize_code_block(self, block):
        content = block.content()
        if block.is_fenced:
            nl = content.find('\n')
            first_line = content[:nl]
            rest = content[nl + 1:]
            block.info = unescape_string(first_line.strip(' \t'))
            block.literal = rest
        else:
            lines = content.split('\n')
            while lines and RE_BLANK_LINE.fullmatch(lines[-1]):
                lines.pop()
            block.literal = '\n'.join(lines) + '\n'
            block.end_line = block.start_line + max(len(lines), 1) - 1
        block.string_content = ''

    def _finalize_list(self, block):
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
        if block.last_child is not None:
            block.end_line = block.last_child.end_line

    # ------------------------------------------------------------------
    # Inline processing
    # ------------------------------------------------------------------
    def process_inlines(self, root):
        stack = [root]
        parser = self.inline_parser
        while stack:
            node = stack.pop()
            if node.type == 'paragraph' or node.type == 'heading':
                parser.parse(node, self.refmap)
            else:
                child = node.first_child
                while child is not None:
                    stack.append(child)
                    child = child.next


def parse(markdown):
    """Parse markdown into a document tree (blocks and inlines)."""
    return BlockParser().parse(markdown)
