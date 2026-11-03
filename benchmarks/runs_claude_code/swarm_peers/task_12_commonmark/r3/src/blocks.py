"""Block-structure parsing for CommonMark 0.31.2.

Public API: ``parse_document(text) -> (root, refmap)``.

The parser follows the two-phase strategy described in the spec's
appendix: lines are consumed one at a time, open container blocks are
matched, new blocks are started, and leaf blocks receive text.  Inline
content (paragraph and heading ``content``) is left as raw strings for
``src.inlines`` to process.
"""

import re

__all__ = ["Node", "parse_document"]


class Node(object):
    """A block node.

    Attributes used by the renderer:
      type      -- document, block_quote, list, item, paragraph, heading,
                   thematic_break, code_block, html_block
      children  -- list of child nodes
      ordered, start, tight          (list)
      level, content                 (heading)
      content                        (paragraph)
      info, literal, fenced          (code_block)
      literal                        (html_block)
    """

    def __init__(self, type_, start_line=0):
        self.type = type_
        self.children = []
        self.parent = None
        self.open = True
        self.start_line = start_line
        self.end_line = start_line
        self.string_content = ""
        # list / item data
        self.list_data = None
        self.ordered = False
        self.start = None
        self.tight = True
        # heading
        self.level = 0
        self.content = None
        # code block
        self.fenced = False
        self.fence_char = None
        self.fence_length = 0
        self.fence_offset = 0
        self.info = ""
        self.literal = None
        # html block
        self.html_block_type = 0

    @property
    def first_child(self):
        return self.children[0] if self.children else None

    @property
    def last_child(self):
        return self.children[-1] if self.children else None

    def append_child(self, child):
        child.parent = self
        self.children.append(child)

    def unlink(self):
        if self.parent is not None:
            self.parent.children.remove(self)
            self.parent = None

    def insert_after(self, sibling):
        """Insert ``sibling`` right after self in the parent's children."""
        parent = self.parent
        idx = parent.children.index(self)
        sibling.parent = parent
        parent.children.insert(idx + 1, sibling)

    def __repr__(self):  # pragma: no cover - debugging aid
        return "Node(%s)" % self.type


# ---------------------------------------------------------------------------
# Regular expressions

_TAGNAME = r"[A-Za-z][A-Za-z0-9-]*"
_ATTRIBUTENAME = r"[a-zA-Z_:][a-zA-Z0-9:._-]*"
_UNQUOTEDVALUE = r"[^\"'=<>`\x00-\x20]+"
_SINGLEQUOTEDVALUE = r"'[^']*'"
_DOUBLEQUOTEDVALUE = r'"[^"]*"'
_ATTRIBUTEVALUE = "(?:%s|%s|%s)" % (_UNQUOTEDVALUE, _SINGLEQUOTEDVALUE,
                                    _DOUBLEQUOTEDVALUE)
_ATTRIBUTEVALUESPEC = r"(?:[ \t\n]*=[ \t\n]*" + _ATTRIBUTEVALUE + ")"
_ATTRIBUTE = r"(?:[ \t\n]+" + _ATTRIBUTENAME + _ATTRIBUTEVALUESPEC + "?)"
_OPENTAG = "<" + _TAGNAME + _ATTRIBUTE + r"*[ \t\n]*/?>"
_CLOSETAG = "</" + _TAGNAME + r"[ \t\n]*>"

_BLOCK_TAGS = (
    "address|article|aside|base|basefont|blockquote|body|caption|center|"
    "col|colgroup|dd|details|dialog|dir|div|dl|dt|fieldset|figcaption|"
    "figure|footer|form|frame|frameset|h[123456]|head|header|hr|html|"
    "iframe|legend|li|link|main|menu|menuitem|nav|noframes|ol|optgroup|"
    "option|p|param|search|section|summary|table|tbody|td|tfoot|th|thead|"
    "title|tr|track|ul")

_RE_HTML_BLOCK_OPEN = [
    None,
    re.compile(r"^<(?:script|pre|textarea|style)(?:[ \t\n\r\f\v]|>|$)", re.I),
    re.compile(r"^<!--"),
    re.compile(r"^<[?]"),
    re.compile(r"^<![A-Za-z]"),
    re.compile(r"^<!\[CDATA\["),
    re.compile(r"^</?(?:" + _BLOCK_TAGS + r")(?:[ \t\n\r\f\v]|/?>|$)", re.I),
    re.compile(r"^(?:" + _OPENTAG + "|" + _CLOSETAG + r")[ \t]*$", re.I),
]

_RE_HTML_BLOCK_CLOSE = [
    None,
    re.compile(r"</(?:script|pre|textarea|style)>", re.I),
    re.compile(r"-->"),
    re.compile(r"\?>"),
    re.compile(r">"),
    re.compile(r"\]\]>"),
]

_RE_MAYBE_SPECIAL = re.compile(r"^[#`~*+_=<>0-9-]")
_RE_ATX_HEADING = re.compile(r"^#{1,6}(?:[ \t]+|$)")
_RE_CODE_FENCE = re.compile(r"^`{3,}(?!.*`)|^~{3,}")
_RE_CLOSING_CODE_FENCE = re.compile(r"^(?:`{3,}|~{3,})(?=[ \t]*$)")
_RE_SETEXT_HEADING = re.compile(r"^(?:=+|-+)[ \t]*$")
_RE_THEMATIC_BREAK = re.compile(
    r"^(?:\*[ \t]*){3,}$|^(?:_[ \t]*){3,}$|^(?:-[ \t]*){3,}$")
_RE_BULLET = re.compile(r"^[*+-]")
_RE_ORDERED = re.compile(r"^(\d{1,9})([.)])")
_RE_LINE_ENDING = re.compile(r"\r\n|\n|\r")
_RE_NONSPACE = re.compile(r"[^ \t\f\v\r\n]")
_RE_SPACE_AT_EOL = re.compile(r"[ \t]*(?:\n|$)")


def _is_space_or_tab(c):
    return c == " " or c == "\t"


def _peek(s, i):
    return s[i] if i < len(s) else ""


def _is_blank(s):
    return _RE_NONSPACE.search(s) is None


# ---------------------------------------------------------------------------
# Link reference definitions

def _spnl(s, pos):
    """Skip spaces/tabs, at most one newline, then spaces/tabs."""
    n = len(s)
    while pos < n and s[pos] in " \t":
        pos += 1
    if pos < n and s[pos] == "\n":
        pos += 1
        while pos < n and s[pos] in " \t":
            pos += 1
    return pos


def _parse_reference(s, refmap):
    """Try to parse a link reference definition at the start of ``s``.

    Returns the number of characters consumed (0 if none)."""
    from . import inlines

    res = inlines.parse_link_label(s, 0)
    if res is None:
        return 0
    rawlabel, pos = res
    if _peek(s, pos) != ":":
        return 0
    pos += 1
    pos = _spnl(s, pos)
    dest_start = pos
    res = inlines.parse_link_destination(s, pos)
    if res is None:
        return 0
    dest, pos = res
    if pos == dest_start or (dest == "" and _peek(s, dest_start) != "<"):
        # empty destinations are only allowed in the form <>
        return 0
    beforetitle = pos
    pos = _spnl(s, pos)
    title = None
    if pos != beforetitle:
        res = inlines.parse_link_title(s, pos)
        if res is not None:
            title, pos = res
    if title is None:
        pos = beforetitle
    m = _RE_SPACE_AT_EOL.match(s, pos)
    if m is None:
        if title is None:
            return 0
        # Title not at line end: drop the title and require the
        # destination to be at the end of its line.
        title = None
        pos = beforetitle
        m = _RE_SPACE_AT_EOL.match(s, pos)
        if m is None:
            return 0
    pos = m.end()
    normlabel = inlines.normalize_label(rawlabel)
    if normlabel == "":
        return 0
    if normlabel not in refmap:
        refmap[normlabel] = (dest, title if title else None)
    return pos


# ---------------------------------------------------------------------------
# Parser

_CONTAINER_TYPES = ("document", "block_quote", "item")


def _can_contain(parent_type, child_type):
    if parent_type in _CONTAINER_TYPES:
        return child_type != "item"
    if parent_type == "list":
        return child_type == "item"
    return False


def _accepts_lines(t):
    return t in ("paragraph", "code_block", "html_block")


class _BlockParser(object):

    def __init__(self):
        self.doc = Node("document", 1)
        self.tip = self.doc
        self.oldtip = self.doc
        self.refmap = {}
        self.line = ""
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
        self.last_line_length = 0
        self._starts = [
            self._start_block_quote,
            self._start_atx_heading,
            self._start_fenced_code,
            self._start_html_block,
            self._start_setext_heading,
            self._start_thematic_break,
            self._start_list_item,
            self._start_indented_code,
        ]

    # -- low level line scanning -------------------------------------------

    def find_next_nonspace(self):
        ln = self.line
        i = self.offset
        cols = self.column
        n = len(ln)
        while i < n:
            c = ln[i]
            if c == " ":
                i += 1
                cols += 1
            elif c == "\t":
                i += 1
                cols += 4 - (cols % 4)
            else:
                break
        self.blank = i >= n
        self.next_nonspace = i
        self.next_nonspace_column = cols
        self.indent = cols - self.column
        self.indented = self.indent >= 4

    def advance_next_nonspace(self):
        self.offset = self.next_nonspace
        self.column = self.next_nonspace_column
        self.partially_consumed_tab = False

    def advance_offset(self, count, columns):
        ln = self.line
        while count > 0 and self.offset < len(ln):
            c = ln[self.offset]
            if c == "\t":
                chars_to_tab = 4 - (self.column % 4)
                if columns:
                    self.partially_consumed_tab = chars_to_tab > count
                    chars_to_advance = min(count, chars_to_tab)
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
            self.offset += 1  # skip over tab
            chars_to_tab = 4 - (self.column % 4)
            self.tip.string_content += " " * chars_to_tab
        self.tip.string_content += self.line[self.offset:] + "\n"

    def add_child(self, tag):
        while not _can_contain(self.tip.type, tag):
            self.finalize(self.tip, self.line_number - 1)
        node = Node(tag, self.line_number)
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

    def continue_block(self, container):
        """0 = matched, 1 = not matched, 2 = matched and line consumed."""
        t = container.type
        ln = self.line
        if t in ("document", "list"):
            return 0
        if t == "block_quote":
            if not self.indented and _peek(ln, self.next_nonspace) == ">":
                self.advance_next_nonspace()
                self.advance_offset(1, False)
                if _is_space_or_tab(_peek(ln, self.offset)):
                    self.advance_offset(1, True)
                return 0
            return 1
        if t == "item":
            ld = container.list_data
            if self.blank:
                if container.first_child is None:
                    return 1
                self.advance_next_nonspace()
            elif self.indent >= ld["marker_offset"] + ld["padding"]:
                self.advance_offset(ld["marker_offset"] + ld["padding"], True)
            else:
                return 1
            return 0
        if t in ("heading", "thematic_break"):
            return 1
        if t == "code_block":
            if container.fenced:
                m = None
                if (not self.indented and
                        _peek(ln, self.next_nonspace) == container.fence_char):
                    m = _RE_CLOSING_CODE_FENCE.match(ln[self.next_nonspace:])
                if m is not None and len(m.group(0)) >= container.fence_length:
                    self.last_line_length = len(ln)
                    self.finalize(container, self.line_number)
                    return 2
                i = container.fence_offset
                while i > 0 and _is_space_or_tab(_peek(ln, self.offset)):
                    self.advance_offset(1, True)
                    i -= 1
            else:
                if self.indent >= 4:
                    self.advance_offset(4, True)
                elif self.blank:
                    self.advance_next_nonspace()
                else:
                    return 1
            return 0
        if t == "html_block":
            if self.blank and container.html_block_type in (6, 7):
                return 1
            return 0
        if t == "paragraph":
            return 1 if self.blank else 0
        return 1

    # -- finalization ------------------------------------------------------

    def finalize(self, block, line_number):
        above = block.parent
        block.open = False
        block.end_line = line_number
        t = block.type
        if t == "paragraph":
            self._finalize_paragraph(block)
        elif t == "code_block":
            content = block.string_content
            if block.fenced:
                nl = content.find("\n")
                first_line = content[:nl] if nl >= 0 else content
                rest = content[nl + 1:] if nl >= 0 else ""
                from . import inlines
                block.info = inlines.unescape_string(
                    first_line.strip(" \t\r\n\f\v"))
                block.literal = rest
            else:
                lines = content.split("\n")
                # content ends with "\n" so the last element is ""
                if lines and lines[-1] == "":
                    lines.pop()
                while lines and lines[-1].strip(" \t") == "":
                    lines.pop()
                block.literal = "".join(l + "\n" for l in lines)
            block.string_content = ""
        elif t == "html_block":
            content = block.string_content
            if content.endswith("\n"):
                content = content[:-1]
            block.literal = content
            block.string_content = ""
        elif t == "item":
            if block.children:
                block.end_line = block.children[-1].end_line
            else:
                block.end_line = block.start_line
        elif t == "list":
            self._finalize_list(block)
        self.tip = above

    def _finalize_paragraph(self, block):
        content = block.string_content
        has_ref = False
        while content.startswith("["):
            pos = _parse_reference(content, self.refmap)
            if pos == 0:
                break
            content = content[pos:]
            has_ref = True
        block.string_content = content
        if has_ref and _is_blank(content):
            block.unlink()
            return
        block.content = content.rstrip(" \t\n\r")

    def _finalize_list(self, block):
        tight = True
        items = block.children
        for i, item in enumerate(items):
            if i + 1 < len(items) and item.end_line < items[i + 1].start_line - 1:
                tight = False
                break
            kids = item.children
            for j in range(len(kids) - 1):
                if kids[j].end_line < kids[j + 1].start_line - 1:
                    tight = False
                    break
            if not tight:
                break
        block.tight = tight
        if block.children:
            block.end_line = block.children[-1].end_line

    # -- block starts ------------------------------------------------------

    def _start_block_quote(self, container):
        if not self.indented and _peek(self.line, self.next_nonspace) == ">":
            self.advance_next_nonspace()
            self.advance_offset(1, False)
            if _is_space_or_tab(_peek(self.line, self.offset)):
                self.advance_offset(1, True)
            self.close_unmatched_blocks()
            self.add_child("block_quote")
            return 1
        return 0

    def _start_atx_heading(self, container):
        if self.indented:
            return 0
        rest = self.line[self.next_nonspace:]
        m = _RE_ATX_HEADING.match(rest)
        if m is None:
            return 0
        self.advance_next_nonspace()
        self.advance_offset(len(m.group(0)), False)
        self.close_unmatched_blocks()
        heading = self.add_child("heading")
        heading.level = len(m.group(0).strip(" \t"))
        content = self.line[self.offset:]
        content = re.sub(r"^[ \t]*#+[ \t]*$", "", content)
        content = re.sub(r"[ \t]+#+[ \t]*$", "", content)
        heading.content = content.strip(" \t")
        self.advance_offset(len(self.line) - self.offset, False)
        return 2

    def _start_fenced_code(self, container):
        if self.indented:
            return 0
        m = _RE_CODE_FENCE.match(self.line[self.next_nonspace:])
        if m is None:
            return 0
        fence_length = len(m.group(0))
        self.close_unmatched_blocks()
        block = self.add_child("code_block")
        block.fenced = True
        block.fence_length = fence_length
        block.fence_char = m.group(0)[0]
        block.fence_offset = self.indent
        self.advance_next_nonspace()
        self.advance_offset(fence_length, False)
        return 2

    def _start_html_block(self, container):
        if self.indented or _peek(self.line, self.next_nonspace) != "<":
            return 0
        s = self.line[self.next_nonspace:]
        for block_type in range(1, 8):
            if _RE_HTML_BLOCK_OPEN[block_type].search(s) and (
                    block_type < 7 or (
                        container.type != "paragraph" and
                        not (not self.all_closed and not self.blank and
                             self.tip.type == "paragraph"))):
                self.close_unmatched_blocks()
                # Keep leading whitespace: do not advance offset.
                block = self.add_child("html_block")
                block.html_block_type = block_type
                return 2
        return 0

    def _start_setext_heading(self, container):
        if self.indented or container.type != "paragraph":
            return 0
        m = _RE_SETEXT_HEADING.match(self.line[self.next_nonspace:])
        if m is None:
            return 0
        self.close_unmatched_blocks()
        # Resolve reference link definitions first.
        content = container.string_content
        while content.startswith("["):
            pos = _parse_reference(content, self.refmap)
            if pos == 0:
                break
            content = content[pos:]
        container.string_content = content
        if content and not _is_blank(content):
            heading = Node("heading", container.start_line)
            heading.level = 1 if m.group(0)[0] == "=" else 2
            heading.content = content.strip(" \t\n\r")
            container.insert_after(heading)
            container.unlink()
            self.tip = heading
            self.advance_offset(len(self.line) - self.offset, False)
            return 2
        return 0

    def _start_thematic_break(self, container):
        if self.indented:
            return 0
        if _RE_THEMATIC_BREAK.match(self.line[self.next_nonspace:]) is None:
            return 0
        self.close_unmatched_blocks()
        self.add_child("thematic_break")
        self.advance_offset(len(self.line) - self.offset, False)
        return 2

    def _parse_list_marker(self, container):
        ln = self.line
        if self.indent >= 4:
            return None
        rest = ln[self.next_nonspace:]
        data = {
            "type": None, "tight": True, "bullet_char": None, "start": None,
            "delimiter": None, "padding": None, "marker_offset": self.indent,
        }
        m = _RE_BULLET.match(rest)
        if m is not None:
            data["type"] = "bullet"
            data["bullet_char"] = m.group(0)[0]
        else:
            m = _RE_ORDERED.match(rest)
            if m is not None and (container.type != "paragraph" or
                                  m.group(1) == "1"):
                data["type"] = "ordered"
                data["start"] = int(m.group(1))
                data["delimiter"] = m.group(2)
            else:
                return None
        mlen = len(m.group(0))
        nextc = _peek(ln, self.next_nonspace + mlen)
        if not (nextc == "" or nextc == " " or nextc == "\t"):
            return None
        if container.type == "paragraph" and _is_blank(
                ln[self.next_nonspace + mlen:]):
            return None
        self.advance_next_nonspace()
        self.advance_offset(mlen, True)
        spaces_start_col = self.column
        spaces_start_offset = self.offset
        while True:
            self.advance_offset(1, True)
            nextc = _peek(ln, self.offset)
            if not (self.column - spaces_start_col < 5 and
                    _is_space_or_tab(nextc)):
                break
        blank_item = _peek(ln, self.offset) == ""
        spaces_after_marker = self.column - spaces_start_col
        if spaces_after_marker >= 5 or spaces_after_marker < 1 or blank_item:
            data["padding"] = mlen + 1
            self.column = spaces_start_col
            self.offset = spaces_start_offset
            self.partially_consumed_tab = False
            if _is_space_or_tab(_peek(ln, self.offset)):
                self.advance_offset(1, True)
        else:
            data["padding"] = mlen + spaces_after_marker
        return data

    def _start_list_item(self, container):
        if self.indented and container.type != "list":
            return 0
        data = self._parse_list_marker(container)
        if data is None:
            return 0
        self.close_unmatched_blocks()
        if self.tip.type != "list" or not _lists_match(self.tip.list_data,
                                                        data):
            lst = self.add_child("list")
            lst.list_data = data
            lst.ordered = data["type"] == "ordered"
            lst.start = data["start"]
        item = self.add_child("item")
        item.list_data = data
        return 1

    def _start_indented_code(self, container):
        if self.indented and self.tip.type != "paragraph" and not self.blank:
            self.advance_offset(4, True)
            self.close_unmatched_blocks()
            self.add_child("code_block")
            return 2
        return 0

    # -- main line routine -------------------------------------------------

    def incorporate_line(self, ln):
        all_matched = True
        container = self.doc
        self.oldtip = self.tip
        self.offset = 0
        self.column = 0
        self.blank = False
        self.partially_consumed_tab = False
        self.line_number += 1
        self.line = ln

        while True:
            last_child = container.last_child
            if last_child is None or not last_child.open:
                break
            container = last_child
            self.find_next_nonspace()
            r = self.continue_block(container)
            if r == 0:
                continue
            elif r == 1:
                container = container.parent
                all_matched = False
                break
            else:  # r == 2: line fully handled (closing code fence)
                self.last_line_length = len(ln)
                return

        self.all_closed = container is self.oldtip
        self.last_matched_container = container

        matched_leaf = (container.type != "paragraph" and
                        _accepts_lines(container.type))
        while not matched_leaf:
            self.find_next_nonspace()
            if (not self.indented and
                    not _RE_MAYBE_SPECIAL.match(ln[self.next_nonspace:])):
                self.advance_next_nonspace()
                break
            res = 0
            for start in self._starts:
                res = start(container)
                if res == 1:
                    container = self.tip
                    break
                elif res == 2:
                    container = self.tip
                    matched_leaf = True
                    break
            if res == 0:
                self.advance_next_nonspace()
                break

        if (not self.all_closed and not self.blank and
                self.tip.type == "paragraph"):
            # lazy paragraph continuation
            self.add_line()
        else:
            self.close_unmatched_blocks()
            t = container.type
            if _accepts_lines(t):
                self.add_line()
                if (t == "html_block" and
                        1 <= container.html_block_type <= 5 and
                        _RE_HTML_BLOCK_CLOSE[container.html_block_type].search(
                            ln[self.offset:])):
                    self.last_line_length = len(ln)
                    self.finalize(container, self.line_number)
            elif self.offset < len(ln) and not self.blank:
                container = self.add_child("paragraph")
                self.advance_next_nonspace()
                self.add_line()
        self.last_line_length = len(ln)

    def parse(self, text):
        text = text.replace("\0", "�")
        lines = _RE_LINE_ENDING.split(text)
        if text and (text.endswith("\n") or text.endswith("\r")):
            lines.pop()
        if text == "":
            lines = []
        for ln in lines:
            self.incorporate_line(ln)
        while self.tip is not None:
            self.finalize(self.tip, len(lines))
        return self.doc, self.refmap


def _lists_match(list_data, item_data):
    return (list_data["type"] == item_data["type"] and
            list_data["delimiter"] == item_data["delimiter"] and
            list_data["bullet_char"] == item_data["bullet_char"])


def parse_document(text):
    """Parse ``text`` into a block tree.

    Returns ``(root, refmap)`` where ``root`` is the document Node and
    ``refmap`` maps normalized labels to ``(href, title)``."""
    return _BlockParser().parse(text)
