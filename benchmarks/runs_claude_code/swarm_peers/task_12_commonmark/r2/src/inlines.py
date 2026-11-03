"""Inline parsing for CommonMark 0.31.2.

Public API:
    render_inlines(text, refmap) -> str   HTML for raw inline content
    normalize_label(label) -> str         reference-label normalization
    unescape_string(s) -> str             backslash escapes + entity references
    escape_html(s) -> str                 escape & < > "
    normalize_uri(s) -> str               percent-encode a link destination
    parse_link_destination(s, pos, allow_empty=False) -> (raw, newpos) | None
    parse_link_title(s, pos) -> (raw, newpos) | None
    parse_link_label(s, pos) -> (raw, newpos) | None
    decode_entity(s) -> str | None        decode one '&...;' reference
"""

import re
import unicodedata
from html.entities import html5 as _HTML5

__all__ = [
    "render_inlines", "parse_inlines", "normalize_label", "unescape_string",
    "escape_html", "normalize_uri", "parse_link_destination",
    "parse_link_title", "parse_link_label", "decode_entity",
]

ASCII_PUNCT = "!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~"
_ASCII_PUNCT_SET = frozenset(ASCII_PUNCT)

ENTITY_RE_SRC = r"&(?:#[xX][0-9a-fA-F]{1,6}|#[0-9]{1,7}|[A-Za-z][A-Za-z0-9]{1,31});"
_ENTITY_RE = re.compile(ENTITY_RE_SRC)
_ESCAPABLE_OR_ENTITY_RE = re.compile(r"\\([!-/:-@\[-`{-~])|(" + ENTITY_RE_SRC + ")")


# ---------------------------------------------------------------- utilities

def escape_html(s):
    if not s:
        return s
    return (s.replace("&", "&amp;").replace("<", "&lt;")
             .replace(">", "&gt;").replace('"', "&quot;"))


def decode_entity(ent):
    """Decode a full entity reference such as '&amp;' or '&#35;'.
    Returns None if it is not a valid reference."""
    if not (ent.startswith("&") and ent.endswith(";")):
        return None
    body = ent[1:-1]
    if body.startswith("#"):
        if body[1:2] in ("x", "X"):
            digits = body[2:]
            if not digits or len(digits) > 6:
                return None
            try:
                cp = int(digits, 16)
            except ValueError:
                return None
        else:
            digits = body[1:]
            if not digits or len(digits) > 7 or not digits.isdigit():
                return None
            cp = int(digits)
        if cp == 0 or 0xD800 <= cp <= 0xDFFF or cp > 0x10FFFF:
            return "\ufffd"
        return chr(cp)
    val = _HTML5.get(body + ";")
    return val


def _unescape_repl(m):
    if m.group(1) is not None:
        return m.group(1)
    ent = m.group(2)
    dec = decode_entity(ent)
    return ent if dec is None else dec


def unescape_string(s):
    if "\\" not in s and "&" not in s:
        return s
    return _ESCAPABLE_OR_ENTITY_RE.sub(_unescape_repl, s)


_WS_COLLAPSE_RE = re.compile(r"[ \t\r\n]+")


def normalize_label(label):
    return _WS_COLLAPSE_RE.sub(" ", label.strip(" \t\r\n")).casefold()


_URI_SAFE = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    ";/?:@&=+$,-_.!~*'()#")
_HEX = frozenset("0123456789abcdefABCDEF")


def normalize_uri(s):
    out = []
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        if c == "%" and i + 2 < n + 0 and s[i + 1] in _HEX and s[i + 2] in _HEX:
            out.append(s[i:i + 3])
            i += 3
            continue
        if c in _URI_SAFE:
            out.append(c)
        else:
            try:
                b = c.encode("utf-8")
            except UnicodeEncodeError:
                b = "\ufffd".encode("utf-8")
            out.append("".join("%%%02X" % x for x in b))
        i += 1
    return "".join(out)


def _is_unicode_whitespace(c):
    return c in "\t\n\f\r " or unicodedata.category(c) == "Zs"


def _is_unicode_punct(c):
    if c in _ASCII_PUNCT_SET:
        return True
    cat = unicodedata.category(c)
    return cat[0] in ("P", "S")


# ------------------------------------------------- link component scanners

def _scan_link_label(s, pos):
    """pos points at '['.  Returns (raw_inner, pos_after_close) or None.
    Does not require non-whitespace content."""
    n = len(s)
    if pos >= n or s[pos] != "[":
        return None
    i = pos + 1
    while i < n:
        c = s[i]
        if c == "\\" and i + 1 < n and s[i + 1] in _ASCII_PUNCT_SET:
            i += 2
        elif c == "[":
            return None
        elif c == "]":
            if i - (pos + 1) > 999:
                return None
            return s[pos + 1:i], i + 1
        else:
            i += 1
        if i - (pos + 1) > 999:
            return None
    return None


def parse_link_label(s, pos):
    """pos points at '['.  Returns (raw_inner, pos_after_close) or None.
    The label must contain at least one non-whitespace character."""
    r = _scan_link_label(s, pos)
    if r is None or not r[0].strip(" \t\r\n"):
        return None
    return r


def parse_link_destination(s, pos, allow_empty=False):
    """Returns (raw_destination, newpos) or None.  For pointy destinations
    the raw value excludes the angle brackets."""
    n = len(s)
    if pos < n and s[pos] == "<":
        i = pos + 1
        while i < n:
            c = s[i]
            if c == "\\" and i + 1 < n and s[i + 1] in _ASCII_PUNCT_SET:
                i += 2
                continue
            if c == ">":
                return s[pos + 1:i], i + 1
            if c in "<\n":
                return None
            i += 1
        return None
    i = pos
    depth = 0
    while i < n:
        c = s[i]
        if c == "\\" and i + 1 < n and s[i + 1] in _ASCII_PUNCT_SET:
            i += 2
            continue
        if c == "(":
            depth += 1
        elif c == ")":
            if depth == 0:
                break
            depth -= 1
        elif ord(c) <= 0x20 or c == "\x7f":
            break
        i += 1
    if depth != 0:
        return None
    if i == pos:
        if allow_empty and i < n and s[i] == ")":
            return "", i
        return None
    return s[pos:i], i


def parse_link_title(s, pos):
    """Returns (raw_title_inner, newpos) or None."""
    n = len(s)
    if pos >= n:
        return None
    opener = s[pos]
    if opener == '"':
        closer = '"'
    elif opener == "'":
        closer = "'"
    elif opener == "(":
        closer = ")"
    else:
        return None
    i = pos + 1
    while i < n:
        c = s[i]
        if c == "\\" and i + 1 < n and s[i + 1] in _ASCII_PUNCT_SET:
            i += 2
            continue
        if c == closer:
            return s[pos + 1:i], i + 1
        if opener == "(" and c == "(":
            return None
        i += 1
    return None


# ------------------------------------------------------------- inline nodes

class Node(object):
    __slots__ = ("t", "literal", "children", "dest", "title", "prev", "next")

    def __init__(self, t, literal=None):
        self.t = t
        self.literal = literal
        self.children = None
        self.dest = None
        self.title = None
        self.prev = None
        self.next = None


class _NodeList(object):
    """Doubly linked list of inline nodes (constant-time splicing)."""
    __slots__ = ("first", "last")

    def __init__(self):
        self.first = None
        self.last = None

    def append(self, node):
        node.next = None
        node.prev = self.last
        if self.last is not None:
            self.last.next = node
        else:
            self.first = node
        self.last = node

    def unlink(self, node):
        if node.prev is not None:
            node.prev.next = node.next
        else:
            self.first = node.next
        if node.next is not None:
            node.next.prev = node.prev
        else:
            self.last = node.prev
        node.prev = node.next = None

    def insert_after(self, ref, node):
        node.prev = ref
        node.next = ref.next
        if ref.next is not None:
            ref.next.prev = node
        else:
            self.last = node
        ref.next = node

    def cut_between(self, a, b):
        """Remove and return (as a Python list) the nodes strictly between
        a and b (b may be None meaning 'to the end')."""
        out = []
        cur = a.next
        while cur is not b:
            out.append(cur)
            cur = cur.next
        for x in out:
            x.prev = x.next = None
        a.next = b
        if b is not None:
            b.prev = a
        else:
            self.last = a
        return out

    def to_list(self):
        out = []
        cur = self.first
        while cur is not None:
            out.append(cur)
            cur = cur.next
        return out


class _Delim(object):
    __slots__ = ("cc", "numdelims", "origdelims", "node", "previous", "next",
                 "can_open", "can_close")


class _Bracket(object):
    __slots__ = ("node", "previous", "previous_delimiter", "index", "image",
                 "active", "bracket_after")


_RE_TEXT = re.compile(r"[^\n\\`*_\[\]!<&]+")
_RE_BACKTICKS = re.compile(r"`+")
_RE_SPNL = re.compile(r"[ \t]*(?:\n[ \t]*)?")
_RE_AUTOLINK = re.compile(r"<([A-Za-z][A-Za-z0-9.+\-]{1,31}:[^<>\x00-\x20]*)>")
_RE_EMAIL = re.compile(
    r"<([a-zA-Z0-9.!#$%&'*+/=?^_`{|}~\-]+@[a-zA-Z0-9]"
    r"(?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?"
    r"(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*)>")

_WS = r"[ \t\n\v\f\r]"
_TAGNAME = r"[A-Za-z][A-Za-z0-9\-]*"
_ATTRNAME = r"[a-zA-Z_:][a-zA-Z0-9_.:\-]*"
_UNQUOTED = r"[^\"'=<>`\x00-\x20]+"
_ATTRVALUE = r"(?:" + _UNQUOTED + r"|'[^']*'|\"[^\"]*\")"
_ATTRVALUESPEC = r"(?:" + _WS + r"*=" + _WS + r"*" + _ATTRVALUE + r")"
_ATTRIBUTE = r"(?:" + _WS + r"+" + _ATTRNAME + _ATTRVALUESPEC + r"?)"
_OPENTAG = r"<" + _TAGNAME + _ATTRIBUTE + r"*" + _WS + r"*/?>"
_CLOSETAG = r"</" + _TAGNAME + _WS + r"*>"
_COMMENT = r"<!-->|<!--->|<!--[\s\S]*?-->"
_PI = r"<\?[\s\S]*?\?>"
_DECL = r"<![A-Za-z]+[^>]*>"
_CDATA = r"<!\[CDATA\[[\s\S]*?\]\]>"
_RE_HTMLTAG = re.compile(
    "(?:" + "|".join([_OPENTAG, _CLOSETAG, _COMMENT, _PI, _DECL, _CDATA]) + ")")


class InlineParser(object):

    def __init__(self, refmap):
        self.refmap = refmap or {}

    def parse(self, subject):
        self.subject = subject
        self.pos = 0
        self.nodes = _NodeList()
        self.delimiters = None
        self.brackets = None
        n = len(subject)
        while self.pos < n:
            self.parse_inline()
        self.process_emphasis(None)
        return self.nodes.to_list()

    # -- helpers
    def peek(self, off=0):
        p = self.pos + off
        if p < len(self.subject):
            return self.subject[p]
        return None

    def add_text(self, s):
        node = Node("text", s)
        self.nodes.append(node)
        return node

    def parse_inline(self):
        c = self.subject[self.pos]
        if c == "\n":
            self.parse_newline()
        elif c == "\\":
            self.parse_backslash()
        elif c == "`":
            self.parse_backticks()
        elif c == "*" or c == "_":
            self.handle_delim(c)
        elif c == "[":
            self.pos += 1
            node = self.add_text("[")
            self.add_bracket(node, self.pos, False)
        elif c == "!":
            if self.peek(1) == "[":
                self.pos += 2
                node = self.add_text("![")
                self.add_bracket(node, self.pos, True)
            else:
                self.pos += 1
                self.add_text("!")
        elif c == "]":
            self.parse_close_bracket()
        elif c == "<":
            if not (self.parse_autolink() or self.parse_html_tag()):
                self.pos += 1
                self.add_text("<")
        elif c == "&":
            self.parse_entity()
        else:
            m = _RE_TEXT.match(self.subject, self.pos)
            if m:
                self.pos = m.end()
                self.add_text(m.group(0))
            else:
                self.pos += 1
                self.add_text(c)

    def parse_newline(self):
        self.pos += 1
        last = self.nodes.last
        if last is not None and last.t == "text" and last.literal.endswith(" "):
            hard = last.literal.endswith("  ")
            last.literal = last.literal.rstrip(" ")
            self.nodes.append(Node("linebreak" if hard else "softbreak"))
        else:
            self.nodes.append(Node("softbreak"))
        s = self.subject
        n = len(s)
        while self.pos < n and s[self.pos] == " ":
            self.pos += 1

    def parse_backslash(self):
        s = self.subject
        self.pos += 1
        c = self.peek()
        if c == "\n":
            self.pos += 1
            self.nodes.append(Node("linebreak"))
            n = len(s)
            while self.pos < n and s[self.pos] == " ":
                self.pos += 1
        elif c is not None and c in _ASCII_PUNCT_SET:
            self.pos += 1
            self.add_text(c)
        else:
            self.add_text("\\")

    def parse_backticks(self):
        s = self.subject
        m = _RE_BACKTICKS.match(s, self.pos)
        ticks = m.group(0)
        after_open = m.end()
        search = after_open
        while True:
            m2 = _RE_BACKTICKS.search(s, search)
            if m2 is None:
                break
            if len(m2.group(0)) == len(ticks):
                content = s[after_open:m2.start()].replace("\n", " ")
                if (len(content) >= 2 and content[0] == " "
                        and content[-1] == " " and content.strip(" ")):
                    content = content[1:-1]
                self.nodes.append(Node("code", content))
                self.pos = m2.end()
                return
            search = m2.end()
        self.pos = after_open
        self.add_text(ticks)

    def parse_autolink(self):
        s = self.subject
        m = _RE_EMAIL.match(s, self.pos)
        if m:
            addr = m.group(1)
            self.pos = m.end()
            node = Node("link")
            node.dest = "mailto:" + addr
            node.title = ""
            node.children = [Node("text", addr)]
            node.literal = "autolink"
            self.nodes.append(node)
            return True
        m = _RE_AUTOLINK.match(s, self.pos)
        if m:
            uri = m.group(1)
            self.pos = m.end()
            node = Node("link")
            node.dest = uri
            node.title = ""
            node.children = [Node("text", uri)]
            node.literal = "autolink"
            self.nodes.append(node)
            return True
        return False

    def parse_html_tag(self):
        m = _RE_HTMLTAG.match(self.subject, self.pos)
        if m:
            self.pos = m.end()
            self.nodes.append(Node("html", m.group(0)))
            return True
        return False

    def parse_entity(self):
        m = _ENTITY_RE.match(self.subject, self.pos)
        if m:
            dec = decode_entity(m.group(0))
            if dec is not None:
                self.pos = m.end()
                self.add_text(dec)
                return
        self.pos += 1
        self.add_text("&")

    # -- emphasis
    def scan_delims(self, cc):
        s = self.subject
        start = self.pos
        i = start
        n = len(s)
        while i < n and s[i] == cc:
            i += 1
        numdelims = i - start
        before = s[start - 1] if start > 0 else "\n"
        after = s[i] if i < n else "\n"
        after_ws = _is_unicode_whitespace(after)
        after_p = _is_unicode_punct(after)
        before_ws = _is_unicode_whitespace(before)
        before_p = _is_unicode_punct(before)
        left = (not after_ws) and (not after_p or before_ws or before_p)
        right = (not before_ws) and (not before_p or after_ws or after_p)
        if cc == "_":
            can_open = left and (not right or before_p)
            can_close = right and (not left or after_p)
        else:
            can_open = left
            can_close = right
        return numdelims, can_open, can_close

    def handle_delim(self, cc):
        numdelims, can_open, can_close = self.scan_delims(cc)
        startpos = self.pos
        self.pos += numdelims
        node = self.add_text(self.subject[startpos:self.pos])
        if can_open or can_close:
            d = _Delim()
            d.cc = cc
            d.numdelims = numdelims
            d.origdelims = numdelims
            d.node = node
            d.previous = self.delimiters
            d.next = None
            d.can_open = can_open
            d.can_close = can_close
            if d.previous is not None:
                d.previous.next = d
            self.delimiters = d

    def remove_delimiter(self, d):
        if d.previous is not None:
            d.previous.next = d.next
        if d.next is not None:
            d.next.previous = d.previous
        else:
            self.delimiters = d.previous

    def process_emphasis(self, stack_bottom):
        openers_bottom = {}
        closer = self.delimiters
        while closer is not None and closer.previous is not stack_bottom:
            closer = closer.previous
        while closer is not None:
            if not closer.can_close:
                closer = closer.next
                continue
            cc = closer.cc
            key = (cc, closer.can_open, closer.origdelims % 3)
            bottom = openers_bottom.get(key, stack_bottom)
            opener = closer.previous
            found = False
            while (opener is not None and opener is not stack_bottom
                   and opener is not bottom):
                odd_match = ((closer.can_open or opener.can_close)
                             and closer.origdelims % 3 != 0
                             and (opener.origdelims + closer.origdelims) % 3 == 0)
                if opener.cc == cc and opener.can_open and not odd_match:
                    found = True
                    break
                opener = opener.previous
            old_closer = closer
            if found:
                use = 2 if (closer.numdelims >= 2 and opener.numdelims >= 2) else 1
                opener_inl = opener.node
                closer_inl = closer.node
                opener.numdelims -= use
                closer.numdelims -= use
                opener_inl.literal = opener_inl.literal[:len(opener_inl.literal) - use]
                closer_inl.literal = closer_inl.literal[:len(closer_inl.literal) - use]
                emph = Node("strong" if use == 2 else "emph")
                emph.children = self.nodes.cut_between(opener_inl, closer_inl)
                self.nodes.insert_after(opener_inl, emph)
                # remove delimiters between opener and closer
                d = closer.previous
                while d is not None and d is not opener:
                    prev = d.previous
                    self.remove_delimiter(d)
                    d = prev
                if opener.numdelims == 0:
                    self.nodes.unlink(opener_inl)
                    self.remove_delimiter(opener)
                if closer.numdelims == 0:
                    self.nodes.unlink(closer_inl)
                    nxt = closer.next
                    self.remove_delimiter(closer)
                    closer = nxt
            else:
                closer = closer.next
                openers_bottom[key] = old_closer.previous
                if not old_closer.can_open:
                    self.remove_delimiter(old_closer)
        while self.delimiters is not None and self.delimiters is not stack_bottom:
            self.remove_delimiter(self.delimiters)

    # -- links
    def add_bracket(self, node, index, image):
        if self.brackets is not None:
            self.brackets.bracket_after = True
        b = _Bracket()
        b.node = node
        b.previous = self.brackets
        b.previous_delimiter = self.delimiters
        b.index = index
        b.image = image
        b.active = True
        b.bracket_after = False
        self.brackets = b

    def remove_bracket(self):
        self.brackets = self.brackets.previous

    def spnl(self):
        m = _RE_SPNL.match(self.subject, self.pos)
        self.pos = m.end()
        return True

    def parse_close_bracket(self):
        s = self.subject
        self.pos += 1
        startpos = self.pos
        opener = self.brackets
        if opener is None:
            self.add_text("]")
            return
        if not opener.active:
            self.add_text("]")
            self.remove_bracket()
            return
        is_image = opener.image
        savepos = self.pos
        matched = False
        dest = None
        title = None
        if self.peek() == "(":
            self.pos += 1
            self.spnl()
            r = parse_link_destination(s, self.pos, allow_empty=True)
            if r is not None:
                dest = unescape_string(r[0])
                self.pos = r[1]
                before_ws_pos = self.pos
                self.spnl()
                if self.pos > before_ws_pos:
                    t = parse_link_title(s, self.pos)
                    if t is not None:
                        title = unescape_string(t[0])
                        self.pos = t[1]
                self.spnl()
                if self.peek() == ")":
                    self.pos += 1
                    matched = True
            if not matched:
                self.pos = savepos
                dest = None
                title = None
        if not matched:
            reflabel = None
            r = _scan_link_label(s, self.pos)
            if r is not None and r[0] != "":
                reflabel = r[0]
                self.pos = r[1]
            else:
                if r is not None:
                    self.pos = r[1]  # collapsed reference "[]"
                if not opener.bracket_after:
                    reflabel = s[opener.index:startpos - 1]
            if reflabel is not None and len(reflabel) <= 999:
                key = normalize_label(reflabel)
                if key and key in self.refmap:
                    dest, title = self.refmap[key]
                    matched = True
            if not matched:
                self.pos = savepos
        if matched:
            node = Node("image" if is_image else "link")
            node.dest = dest
            node.title = title
            self.process_emphasis(opener.previous_delimiter)
            node.children = self.nodes.cut_between(opener.node, None)
            self.nodes.unlink(opener.node)
            self.nodes.append(node)
            self.remove_bracket()
            if not is_image:
                b = self.brackets
                while b is not None:
                    if not b.image:
                        b.active = False
                    b = b.previous
        else:
            self.remove_bracket()
            self.pos = startpos
            self.add_text("]")


# ----------------------------------------------------------------- render

def _render_nodes(nodes, out):
    # Iterative to cope with deeply nested emphasis/links.
    stack = [iter(nodes)]
    closers = [None]
    while stack:
        node = next(stack[-1], None)
        if node is None:
            stack.pop()
            closing = closers.pop()
            if closing:
                out.append(closing)
            continue
        t = node.t
        if t == "text":
            out.append(escape_html(node.literal))
        elif t == "softbreak":
            out.append("\n")
        elif t == "linebreak":
            out.append("<br />\n")
        elif t == "code":
            out.append("<code>" + escape_html(node.literal) + "</code>")
        elif t == "html":
            out.append(node.literal)
        elif t == "emph":
            out.append("<em>")
            stack.append(iter(node.children))
            closers.append("</em>")
        elif t == "strong":
            out.append("<strong>")
            stack.append(iter(node.children))
            closers.append("</strong>")
        elif t == "link":
            out.append('<a href="' + escape_html(normalize_uri(node.dest)) + '"')
            if node.title:
                out.append(' title="' + escape_html(node.title) + '"')
            out.append(">")
            stack.append(iter(node.children))
            closers.append("</a>")
        elif t == "image":
            out.append('<img src="' + escape_html(normalize_uri(node.dest))
                       + '" alt="')
            alt = []
            _render_plain(node.children, alt)
            out.append(escape_html("".join(alt)))
            out.append('"')
            if node.title:
                out.append(' title="' + escape_html(node.title) + '"')
            out.append(" />")


def _render_plain(nodes, out):
    stack = [iter(nodes)]
    while stack:
        node = next(stack[-1], None)
        if node is None:
            stack.pop()
            continue
        t = node.t
        if t in ("text", "code", "html"):
            out.append(node.literal)
        elif t in ("softbreak", "linebreak"):
            out.append("\n")
        elif node.children:
            stack.append(iter(node.children))


def parse_inlines(text, refmap=None):
    return InlineParser(refmap).parse(text)


def render_inlines(text, refmap=None):
    nodes = InlineParser(refmap).parse(text)
    out = []
    _render_nodes(nodes, out)
    return "".join(out)
