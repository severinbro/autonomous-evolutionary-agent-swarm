"""Block-structure parsing for CommonMark 0.31.2.

Public API:
    parse_document(text) -> (root, refmap)
    render_blocks(root, refmap) -> str

The parser follows the two-phase strategy described in the spec's appendix:
lines are consumed one at a time, matching open container blocks, opening new
blocks and adding text to the innermost open leaf.  Link reference definitions
are extracted when paragraphs are closed; inline content is parsed afterwards
(at render time) through ``inlines.render_inlines``.
"""

import re

from . import inlines

# ---------------------------------------------------------------------------
# Regular expressions
# ---------------------------------------------------------------------------

_TAGNAME = r"[A-Za-z][A-Za-z0-9-]*"
_ATTRIBUTENAME = r"[a-zA-Z_:][a-zA-Z0-9_.:-]*"
_UNQUOTEDVALUE = r"[^\"'=<>`\x00-\x20]+"
_SINGLEQUOTEDVALUE = r"'[^']*'"
_DOUBLEQUOTEDVALUE = r'"[^"]*"'
_ATTRIBUTEVALUE = "(?:" + _UNQUOTEDVALUE + "|" + _SINGLEQUOTEDVALUE + "|" + _DOUBLEQUOTEDVALUE + ")"
_ATTRIBUTEVALUESPEC = r"(?:[ \t\n]*=[ \t\n]*" + _ATTRIBUTEVALUE + ")"
_ATTRIBUTE = r"(?:[ \t\n]+" + _ATTRIBUTENAME + _ATTRIBUTEVALUESPEC + "?)"
_OPENTAG = "<" + _TAGNAME + _ATTRIBUTE + r"*[ \t\n]*/?>"
_CLOSETAG = "</" + _TAGNAME + r"[ \t\n]*>"

_BLOCK_TAGS = (
    "address|article|aside|base|basefont|blockquote|body|caption|center|col|"
    "colgroup|dd|details|dialog|dir|div|dl|dt|fieldset|figcaption|figure|"
    "footer|form|frame|frameset|h[123456]|head|header|hr|html|iframe|legend|"
    "li|link|main|menu|menuitem|nav|noframes|ol|optgroup|option|p|param|"
    "search|section|summary|table|tbody|td|tfoot|th|thead|title|tr|track|ul"
)

_HTML_BLOCK_OPEN = [
    None,
    re.compile(r"^<(?:script|pre|textarea|style)(?:[ \t]|>|$)", re.I),
    re.compile(r"^<!--"),
    re.compile(r"^<[?]"),
    re.compile(r"^<![A-Za-z]"),
    re.compile(r"^<!\[CDATA\["),
    re.compile(r"^</?(?:" + _BLOCK_TAGS + r")(?:[ \t]|/?>|$)", re.I),
    re.compile(r"^(?:" + _OPENTAG + "|" + _CLOSETAG + r")[ \t]*$", re.I),
]

_HTML_BLOCK_CLOSE = [
    None,
    re.compile(r"</(?:script|pre|textarea|style)>", re.I),
    re.compile(r"-->"),
    re.compile(r"\?>"),
    re.compile(r">"),
    re.compile(r"\]\]>"),
]

_RE_MAYBE_SPECIAL = re.compile(r"^[#`~*+_=<>0-9-]")
_RE_NONSPACE = re.compile(r"[^ \t\f\v\r\n]")
_RE_BULLET_MARKER = re.compile(r"^[*+-]")
_RE_ORDERED_MARKER = re.compile(r"^(\d{1,9})([.)])")
_RE_ATX_MARKER = re.compile(r"^#{1,6}(?:[ \t]+|$)")
_RE_CODE_FENCE = re.compile(r"^`{3,}(?!.*`)|^~{3,}")
_RE_CLOSING_FENCE = re.compile(r"^(?:`{3,}|~{3,})(?=[ \t]*$)")
_RE_SETEXT = re.compile(r"^(?:=+|-+)[ \t]*$")
_RE_THEMATIC = re.compile(r"^(?:\*[ \t]*){3,}$|^(?:_[ \t]*){3,}$|^(?:-[ \t]*){3,}$")
_RE_LINE_ENDING = re.compile(r"\r\n|\n|\r")

CODE_INDENT = 4


def _peek(s, i):
    return s[i] if 0 <= i < len(s) else ""


def _is_space_or_tab(c):
    return c == " " or c == "\t"


def _is_blank(s):
    return _RE_NONSPACE.search(s) is None


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------


class Node:
    """A block node.

    ``type`` is one of: document, block_quote, list, item, paragraph,
    heading, code_block, html_block, thematic_break.
    """

    def __init__(self, type_, start_line=0):
        self.type = type_
        self.parent = None
        self.children = []
        self.open = True
        self.string_content = ""
        self.start_line = start_line
        self.end_line = start_line
        # heading
        self.level = 0
        # code block
        self.fenced = False
        self.fence_char = ""
        self.fence_length = 0
        self.fence_offset = 0
        self.info = ""
        self.literal = ""
        # html block
        self.html_block_type = 0
        # list / item
        self.list_data = None
        self.tight = True

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

    def replace_with(self, other):
        parent = self.parent
        idx = parent.children.index(self)
        parent.children[idx] = other
        other.parent = parent
        self.parent = None

    def __repr__(self):  # pragma: no cover - debugging aid
        return "Node(%s, %r)" % (self.type, self.children)


_CAN_CONTAIN = {
    "document": lambda t: t != "item",
    "list": lambda t: t == "item",
    "block_quote": lambda t: t != "item",
    "item": lambda t: t != "item",
}

_ACCEPTS_LINES = {"paragraph", "code_block", "html_block"}


def _can_contain(parent_type, child_type):
    f = _CAN_CONTAIN.get(parent_type)
    return f(child_type) if f else False


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


class BlockParser:
    def __init__(self):
        self.doc = Node("document", 1)
        self.tip = self.doc
        self.oldtip = self.doc
        self.refmap = {}
        self.line_number = 0
        self.last_matched_container = self.doc
        self.current_line = ""
        self.offset = 0
        self.column = 0
        self.next_nonspace = 0
        self.next_nonspace_column = 0
        self.indent = 0
        self.indented = False
        self.blank = False
        self.partially_consumed_tab = False
        self.all_closed = True

    # -- line position helpers ------------------------------------------------

    def find_next_nonspace(self):
        line = self.current_line
        i = self.offset
        cols = self.column
        n = len(line)
        while i < n:
            c = line[i]
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
        self.tip.string_content += self.current_line[self.offset:] + "\n"

    def add_child(self, type_):
        while not _can_contain(self.tip.type, type_):
            self.finalize(self.tip, self.line_number - 1)
        node = Node(type_, self.line_number)
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

    # -- continuation ---------------------------------------------------------

    def _continue(self, container):
        """Return 0 if matched, 1 if not matched, 2 if the line is consumed."""
        t = container.type
        if t in ("document", "list"):
            return 0
        if t == "block_quote":
            if not self.indented and _peek(self.current_line, self.next_nonspace) == ">":
                self.advance_next_nonspace()
                self.advance_offset(1, False)
                if _is_space_or_tab(_peek(self.current_line, self.offset)):
                    self.advance_offset(1, True)
                return 0
            return 1
        if t == "item":
            data = container.list_data
            if self.blank:
                if not container.children:
                    return 1
                self.advance_next_nonspace()
            elif self.indent >= data["marker_offset"] + data["padding"]:
                self.advance_offset(data["marker_offset"] + data["padding"], True)
            else:
                return 1
            return 0
        if t in ("heading", "thematic_break"):
            return 1
        if t == "code_block":
            if container.fenced:
                line = self.current_line
                m = None
                if not self.indented and _peek(line, self.next_nonspace) == container.fence_char:
                    m = _RE_CLOSING_FENCE.match(line[self.next_nonspace:])
                if m and len(m.group(0)) >= container.fence_length:
                    self.last_line_length = len(line)
                    self.finalize(container, self.line_number)
                    return 2
                i = container.fence_offset
                while i > 0 and _is_space_or_tab(_peek(line, self.offset)):
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
        if t == "html_block":
            if self.blank and container.html_block_type in (6, 7):
                return 1
            return 0
        if t == "paragraph":
            return 1 if self.blank else 0
        return 0

    # -- finalization ---------------------------------------------------------

    def finalize(self, block, line_number):
        above = block.parent
        block.open = False
        block.end_line = line_number
        t = block.type
        if t == "paragraph":
            content = block.string_content
            pos = 0
            has_defs = False
            while _peek(content, pos) == "[":
                newpos = inlines.parse_reference_definition(content, pos, self.refmap)
                if newpos is None or newpos < 0 or newpos <= pos:
                    break
                pos = newpos
                has_defs = True
            if has_defs:
                block.string_content = content[pos:]
            if _is_blank(block.string_content):
                block.unlink()
        elif t == "code_block":
            content = block.string_content
            if block.fenced:
                nl = content.find("\n")
                first_line = content[:nl] if nl >= 0 else content
                rest = content[nl + 1:] if nl >= 0 else ""
                block.info = inlines.unescape_string(first_line.strip(" \t\n"))
                block.literal = rest
            else:
                lines = content.split("\n")
                while lines and re.match(r"^[ \t]*$", lines[-1]):
                    lines.pop()
                block.literal = "\n".join(lines) + "\n"
        elif t == "html_block":
            block.literal = re.sub(r"(\n *)+$", "", block.string_content)
        elif t == "item":
            if block.children:
                block.end_line = block.children[-1].end_line
            else:
                block.end_line = block.start_line
        elif t == "list":
            if block.children:
                block.end_line = block.children[-1].end_line
            tight = True
            items = block.children
            for idx, item in enumerate(items):
                if idx + 1 < len(items) and _ends_with_blank_line(item, items[idx + 1]):
                    tight = False
                    break
                subs = item.children
                for j, sub in enumerate(subs):
                    if j + 1 < len(subs) and _ends_with_blank_line(sub, subs[j + 1]):
                        tight = False
                        break
                if not tight:
                    break
            block.tight = tight
        self.tip = above

    # -- block starts ---------------------------------------------------------

    def _start_block_quote(self, container):
        if not self.indented and _peek(self.current_line, self.next_nonspace) == ">":
            self.advance_next_nonspace()
            self.advance_offset(1, False)
            if _is_space_or_tab(_peek(self.current_line, self.offset)):
                self.advance_offset(1, True)
            self.close_unmatched_blocks()
            self.add_child("block_quote")
            return 1
        return 0

    def _start_atx_heading(self, container):
        if self.indented:
            return 0
        m = _RE_ATX_MARKER.match(self.current_line[self.next_nonspace:])
        if not m:
            return 0
        self.advance_next_nonspace()
        self.advance_offset(len(m.group(0)), False)
        self.close_unmatched_blocks()
        node = self.add_child("heading")
        node.level = len(m.group(0).strip(" \t"))
        rest = self.current_line[self.offset:]
        rest = re.sub(r"^[ \t]*#+[ \t]*$", "", rest)
        rest = re.sub(r"[ \t]+#+[ \t]*$", "", rest)
        node.string_content = rest
        self.advance_offset(len(self.current_line) - self.offset, False)
        return 2

    def _start_fenced_code(self, container):
        if self.indented:
            return 0
        m = _RE_CODE_FENCE.match(self.current_line[self.next_nonspace:])
        if not m:
            return 0
        fence_length = len(m.group(0))
        self.close_unmatched_blocks()
        node = self.add_child("code_block")
        node.fenced = True
        node.fence_length = fence_length
        node.fence_char = m.group(0)[0]
        node.fence_offset = self.indent
        self.advance_next_nonspace()
        self.advance_offset(fence_length, False)
        return 2

    def _start_html_block(self, container):
        if self.indented or _peek(self.current_line, self.next_nonspace) != "<":
            return 0
        s = self.current_line[self.next_nonspace:]
        for block_type in range(1, 8):
            if _HTML_BLOCK_OPEN[block_type].search(s) and (
                block_type < 7
                or (
                    container.type != "paragraph"
                    and not (not self.all_closed and not self.blank and self.tip.type == "paragraph")
                )
            ):
                self.close_unmatched_blocks()
                node = self.add_child("html_block")
                node.html_block_type = block_type
                return 2
        return 0

    def _start_setext_heading(self, container):
        if self.indented or container.type != "paragraph":
            return 0
        m = _RE_SETEXT.match(self.current_line[self.next_nonspace:])
        if not m:
            return 0
        self.close_unmatched_blocks()
        content = container.string_content
        pos = 0
        while _peek(content, pos) == "[":
            newpos = inlines.parse_reference_definition(content, pos, self.refmap)
            if newpos is None or newpos < 0 or newpos <= pos:
                break
            pos = newpos
        content = content[pos:]
        container.string_content = content
        if content and not _is_blank(content):
            heading = Node("heading", container.start_line)
            heading.level = 1 if m.group(0)[0] == "=" else 2
            heading.string_content = content
            container.replace_with(heading)
            self.tip = heading
            self.advance_offset(len(self.current_line) - self.offset, False)
            return 2
        return 0

    def _start_thematic_break(self, container):
        if self.indented:
            return 0
        if _RE_THEMATIC.match(self.current_line[self.next_nonspace:]):
            self.close_unmatched_blocks()
            self.add_child("thematic_break")
            self.advance_offset(len(self.current_line) - self.offset, False)
            return 2
        return 0

    def _parse_list_marker(self, container):
        if self.indent >= 4:
            return None
        line = self.current_line
        rest = line[self.next_nonspace:]
        data = {
            "type": None,
            "bullet_char": None,
            "start": None,
            "delimiter": None,
            "padding": None,
            "marker_offset": self.indent,
        }
        m = _RE_BULLET_MARKER.match(rest)
        if m:
            data["type"] = "bullet"
            data["bullet_char"] = m.group(0)[0]
        else:
            m = _RE_ORDERED_MARKER.match(rest)
            if m and (container.type != "paragraph" or int(m.group(1)) == 1):
                data["type"] = "ordered"
                data["start"] = int(m.group(1))
                data["delimiter"] = m.group(2)
            else:
                return None
        marker_len = len(m.group(0))
        nextc = _peek(line, self.next_nonspace + marker_len)
        if not (nextc == "" or nextc == "\t" or nextc == " "):
            return None
        if container.type == "paragraph" and _is_blank(line[self.next_nonspace + marker_len:]):
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
        blank_item = _peek(line, self.offset) == ""
        spaces_after_marker = self.column - spaces_start_col
        if spaces_after_marker >= 5 or spaces_after_marker < 1 or blank_item:
            data["padding"] = marker_len + 1
            self.column = spaces_start_col
            self.offset = spaces_start_offset
            if _is_space_or_tab(_peek(line, self.offset)):
                self.advance_offset(1, True)
        else:
            data["padding"] = marker_len + spaces_after_marker
        return data

    def _start_list_item(self, container):
        if self.indented and container.type != "list":
            return 0
        data = self._parse_list_marker(container)
        if data is None:
            return 0
        self.close_unmatched_blocks()
        if self.tip.type != "list" or not _lists_match(container.list_data, data):
            lst = self.add_child("list")
            lst.list_data = data
        item = self.add_child("item")
        item.list_data = data
        return 1

    def _start_indented_code(self, container):
        if self.indented and self.tip.type != "paragraph" and not self.blank:
            self.advance_offset(CODE_INDENT, True)
            self.close_unmatched_blocks()
            self.add_child("code_block")
            return 2
        return 0

    # -- main line routine ----------------------------------------------------

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
            res = self._continue(container)
            if res == 1:
                all_matched = False
            elif res == 2:
                self.last_line_length = len(ln)
                return
            if not all_matched:
                container = container.parent
                break

        self.all_closed = container is self.oldtip
        self.last_matched_container = container

        matched_leaf = container.type != "paragraph" and container.type in _ACCEPTS_LINES
        starts = (
            self._start_block_quote,
            self._start_atx_heading,
            self._start_fenced_code,
            self._start_html_block,
            self._start_setext_heading,
            self._start_thematic_break,
            self._start_list_item,
            self._start_indented_code,
        )
        while not matched_leaf:
            self.find_next_nonspace()
            if not self.indented and not _RE_MAYBE_SPECIAL.match(ln[self.next_nonspace:]):
                self.advance_next_nonspace()
                break
            matched_any = False
            for start in starts:
                res = start(container)
                if res == 1:
                    container = self.tip
                    matched_any = True
                    break
                if res == 2:
                    container = self.tip
                    matched_leaf = True
                    matched_any = True
                    break
            if not matched_any:
                self.advance_next_nonspace()
                break

        if not self.all_closed and not self.blank and self.tip.type == "paragraph":
            # lazy paragraph continuation
            self.add_line()
        else:
            self.close_unmatched_blocks()
            t = container.type
            if t in _ACCEPTS_LINES:
                self.add_line()
                if (
                    t == "html_block"
                    and 1 <= container.html_block_type <= 5
                    and _HTML_BLOCK_CLOSE[container.html_block_type].search(self.current_line[self.offset:])
                ):
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


def _ends_with_blank_line(block, next_block):
    return block.end_line != next_block.start_line - 1


def _lists_match(a, b):
    if a is None:
        return False
    return a["type"] == b["type"] and a["delimiter"] == b["delimiter"] and a["bullet_char"] == b["bullet_char"]


def parse_document(text):
    """Parse ``text`` into a block tree. Returns ``(root, refmap)``."""
    return BlockParser().parse(text)


# ---------------------------------------------------------------------------
# HTML rendering of the block tree
# ---------------------------------------------------------------------------


class _Out:
    def __init__(self):
        self.parts = []
        self.last = "\n"

    def lit(self, s):
        if s:
            self.parts.append(s)
            self.last = s[-1]

    def cr(self):
        if self.last != "\n":
            self.lit("\n")


def _inline_text(node):
    return node.string_content.strip(" \t\n")


def _render_leaf(node, out, refmap):
    t = node.type
    if t == "paragraph":
        gp = node.parent.parent if node.parent is not None else None
        tight = gp is not None and gp.type == "list" and gp.tight
        if not tight:
            out.cr()
            out.lit("<p>")
        out.lit(inlines.render_inlines(_inline_text(node), refmap))
        if not tight:
            out.lit("</p>")
            out.cr()
    elif t == "heading":
        tag = "h%d" % node.level
        out.cr()
        out.lit("<" + tag + ">")
        out.lit(inlines.render_inlines(_inline_text(node), refmap))
        out.lit("</" + tag + ">")
        out.cr()
    elif t == "code_block":
        words = node.info.split() if node.info else []
        attrs = ""
        if words and words[0]:
            attrs = ' class="language-' + inlines.escape_html(words[0]) + '"'
        out.cr()
        out.lit("<pre><code" + attrs + ">")
        out.lit(inlines.escape_html(node.literal))
        out.lit("</code></pre>")
        out.cr()
    elif t == "html_block":
        out.cr()
        out.lit(node.literal)
        out.cr()
    elif t == "thematic_break":
        out.cr()
        out.lit("<hr />")
        out.cr()


def _list_tag(node):
    data = node.list_data
    tag = "ul" if data["type"] == "bullet" else "ol"
    start = data["start"]
    attrs = ""
    if tag == "ol" and start is not None and start != 1:
        attrs = ' start="%d"' % start
    return tag, attrs


def _render_container(node, entering, out):
    t = node.type
    if t == "block_quote":
        if entering:
            out.cr()
            out.lit("<blockquote>")
            out.cr()
        else:
            out.cr()
            out.lit("</blockquote>")
            out.cr()
    elif t == "list":
        tag, attrs = _list_tag(node)
        if entering:
            out.cr()
            out.lit("<" + tag + attrs + ">")
            out.cr()
        else:
            out.cr()
            out.lit("</" + tag + ">")
            out.cr()
    elif t == "item":
        if entering:
            out.lit("<li>")
        else:
            out.lit("</li>")
            out.cr()


_CONTAINERS = ("document", "block_quote", "list", "item")


def _render_node(root, out, refmap):
    # Iterative walk (no recursion) so deeply nested input cannot overflow.
    stack = [(root, False)]
    while stack:
        node, exiting = stack.pop()
        if node.type in _CONTAINERS:
            if exiting:
                _render_container(node, False, out)
                continue
            _render_container(node, True, out)
            stack.append((node, True))
            for child in reversed(node.children):
                stack.append((child, False))
        else:
            _render_leaf(node, out, refmap)


def render_blocks(root, refmap):
    """Render a block tree produced by :func:`parse_document` to HTML."""
    out = _Out()
    _render_node(root, out, refmap)
    return "".join(out.parts)
