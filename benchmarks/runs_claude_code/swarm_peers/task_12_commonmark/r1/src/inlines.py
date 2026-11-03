"""Inline parsing for the CommonMark renderer (spec version 0.31.2).

Public API (see .swarm/board.md):
    render_inlines(text, refmap) -> str
    parse_reference_definition(text, pos, refmap) -> int  (-1 on failure)
    normalize_label(label) -> str
    unescape_string(s) -> str
    escape_html(s) -> str
    normalize_uri(s) -> str
    parse_link_label / parse_link_destination / parse_link_title helpers
"""

import re
import unicodedata
from html.entities import html5 as _HTML5

__all__ = [
    "render_inlines",
    "parse_inlines",
    "parse_reference_definition",
    "normalize_label",
    "unescape_string",
    "escape_html",
    "normalize_uri",
    "parse_link_label",
    "parse_link_destination",
    "parse_link_title",
]

# ---------------------------------------------------------------------------
# Character classes and small helpers
# ---------------------------------------------------------------------------

ESCAPABLE = "!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~"
_ESCAPABLE_SET = frozenset(ESCAPABLE)

_ENTITY_PAT = r"&(?:#[xX][0-9a-fA-F]{1,6}|#[0-9]{1,7}|[A-Za-z][A-Za-z0-9]{1,31});"
_ENTITY_RE = re.compile(_ENTITY_PAT)
_ESC_OR_ENTITY_RE = re.compile(r"\\([!-/:-@\[-`{-~])|" + _ENTITY_PAT)


def _decode_entity(s):
    """Decode an entity/numeric reference (including '&' and ';').

    Returns None when it is not a valid named entity."""
    if s[1] == "#":
        if s[2] in "xX":
            n = int(s[3:-1], 16)
        else:
            n = int(s[2:-1])
        if n == 0 or n > 0x10FFFF or 0xD800 <= n <= 0xDFFF:
            return "\uFFFD"
        return chr(n)
    return _HTML5.get(s[1:])


def unescape_string(s):
    """Process backslash escapes and entity / numeric character references."""
    if "\\" not in s and "&" not in s:
        return s

    def repl(m):
        if m.group(1) is not None:
            return m.group(1)
        d = _decode_entity(m.group(0))
        return m.group(0) if d is None else d

    return _ESC_OR_ENTITY_RE.sub(repl, s)


def escape_html(s):
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


_URI_SAFE = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    ";/?:@&=+$,-_.!~*'()#"
)
_HEX = frozenset("0123456789abcdefABCDEF")


def normalize_uri(uri):
    """Percent-encode a URI the way the reference implementation does
    (existing valid %XX escapes are preserved)."""
    out = []
    i = 0
    n = len(uri)
    while i < n:
        c = uri[i]
        if c in _URI_SAFE:
            out.append(c)
        elif c == "%" and i + 2 < n and uri[i + 1] in _HEX and uri[i + 2] in _HEX:
            out.append(uri[i:i + 3])
            i += 3
            continue
        else:
            cp = ord(c)
            if 0xD800 <= cp <= 0xDFFF:
                c = "\uFFFD"
            for b in c.encode("utf-8"):
                out.append("%%%02X" % b)
        i += 1
    return "".join(out)


def normalize_label(label):
    """Normalize a link label for matching: strip, collapse whitespace,
    Unicode case fold."""
    return " ".join(label.split()).casefold() if label.strip(" \t\n\r\f\v") else ""


def _is_unicode_whitespace(c):
    return c in "\t\n\f\r " or unicodedata.category(c) == "Zs"


def _is_unicode_punct(c):
    return unicodedata.category(c)[0] in "PS"


# ---------------------------------------------------------------------------
# Regular expressions for inline constructs
# ---------------------------------------------------------------------------

_TAGNAME = r"[A-Za-z][A-Za-z0-9-]*"
_ATTRNAME = r"[a-zA-Z_:][a-zA-Z0-9:._-]*"
_UNQUOTED = r"[^\"'=<>`\x00-\x20]+"
_SQUOTED = r"'[^']*'"
_DQUOTED = r'"[^"]*"'
_WS = r"[ \t\n]"
_ATTRVALUE = "(?:" + _UNQUOTED + "|" + _SQUOTED + "|" + _DQUOTED + ")"
_ATTRVALUESPEC = "(?:" + _WS + "*=" + _WS + "*" + _ATTRVALUE + ")"
_ATTRIBUTE = "(?:" + _WS + "+" + _ATTRNAME + _ATTRVALUESPEC + "?)"
_OPENTAG = "<" + _TAGNAME + _ATTRIBUTE + "*" + _WS + "*/?>"
_CLOSETAG = "</" + _TAGNAME + _WS + "*>"
_COMMENT = r"<!-->|<!--->|<!--[\s\S]*?-->"
_PI = r"<\?[\s\S]*?\?>"
_DECL = r"<![A-Za-z][^>]*>"
_CDATA = r"<!\[CDATA\[[\s\S]*?\]\]>"
_HTMLTAG_RE = re.compile(
    "(?:" + "|".join([_OPENTAG, _CLOSETAG, _COMMENT, _PI, _DECL, _CDATA]) + ")"
)
_TAG_RE = re.compile("(?:" + _OPENTAG + "|" + _CLOSETAG + ")")

_AUTOLINK_RE = re.compile(r"<([A-Za-z][A-Za-z0-9.+-]{1,31}:[^<>\x00-\x20]*)>")
_EMAIL_RE = re.compile(
    r"<([a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9]"
    r"(?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?"
    r"(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*)>"
)
_LINK_LABEL_RE = re.compile(r"\[(?:[^\\\[\]]|\\.){0,1000}\]", re.S)
_POINTY_DEST_RE = re.compile(r"<((?:[^<>\n\\]|\\.)*)>")
_TICKS_RE = re.compile(r"`+")
_MAX_LINK_PARENS = 32
_DEST_CHUNK_RE = re.compile(r"[^\\()\x00-\x20\x7f]+")
_TEXT_RE = re.compile(r"[^\n`\[\]\\!<&*_]+")
_SPNL_RE = re.compile(r"[ \t]*(?:\n[ \t]*)?")
_LINE_END_RE = re.compile(r"[ \t]*(?:\n|$)")


# ---------------------------------------------------------------------------
# Link component parsers (shared by inline links and reference definitions)
# ---------------------------------------------------------------------------

def parse_link_label(s, pos):
    """s[pos] should be '['. Returns (inner_label, new_pos) or None."""
    m = _LINK_LABEL_RE.match(s, pos)
    if m is None or m.end() - m.start() > 1001:
        return None
    return s[pos + 1:m.end() - 1], m.end()


def parse_link_destination(s, pos):
    """Returns (raw_destination, new_pos) or None.  The destination is
    returned still escaped (apply unescape_string)."""
    m = _POINTY_DEST_RE.match(s, pos)
    if m is not None:
        return m.group(1), m.end()
    if pos < len(s) and s[pos] == "<":
        return None
    start = pos
    n = len(s)
    parens = 0
    c = ""
    while pos < n:
        m = _DEST_CHUNK_RE.match(s, pos)
        if m is not None:
            pos = m.end()
            if pos >= n:
                break
        c = s[pos]
        if c == "\\" and pos + 1 < n and s[pos + 1] in _ESCAPABLE_SET:
            pos += 2
            continue
        if c == "(":
            parens += 1
            if parens > _MAX_LINK_PARENS:
                # The spec allows implementations to limit nesting depth
                # (the reference C implementation uses 32).
                return None
            pos += 1
        elif c == ")":
            if parens < 1:
                break
            parens -= 1
            pos += 1
        elif ord(c) <= 0x20 or ord(c) == 0x7F:
            break
        else:
            pos += 1
    if pos >= n:
        c = ""
    if pos == start and c != ")":
        return None
    if parens != 0:
        return None
    return s[start:pos], pos


def parse_link_title(s, pos):
    """s[pos] in '"', "'", '('.  Returns (raw_title, new_pos) or None."""
    if pos >= len(s):
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
    n = len(s)
    while i < n:
        c = s[i]
        if c == "\\" and i + 1 < n:
            i += 2
            continue
        if c == closer:
            return s[pos + 1:i], i + 1
        if opener == "(" and c == "(":
            return None
        i += 1
    return None


def parse_reference_definition(text, pos, refmap):
    """Try to parse one link reference definition at text[pos:].

    On success, store it in refmap (if the label is new) and return the
    position just after the definition (after its line ending).  Return -1
    on failure."""
    r = parse_link_label(text, pos)
    if r is None:
        return -1
    rawlabel, p = r
    if p >= len(text) or text[p] != ":":
        return -1
    p += 1
    p = _SPNL_RE.match(text, p).end()
    r = parse_link_destination(text, p)
    if r is None:
        return -1
    rawdest, p = r
    dest = unescape_string(rawdest)
    beforetitle = p
    p = _SPNL_RE.match(text, p).end()
    title = None
    if p != beforetitle:
        r = parse_link_title(text, p)
        if r is not None:
            title = unescape_string(r[0])
            p = r[1]
    if title is None:
        p = beforetitle
    m = _LINE_END_RE.match(text, p)
    if m is None:
        if title is None:
            return -1
        # The title is not followed by a line end; the definition may still
        # be valid without it.
        title = None
        p = beforetitle
        m = _LINE_END_RE.match(text, p)
        if m is None:
            return -1
    p = m.end()
    key = normalize_label(rawlabel)
    if key == "":
        return -1
    if key not in refmap:
        refmap[key] = {"destination": dest, "title": title}
    return p


# ---------------------------------------------------------------------------
# Inline node tree
# ---------------------------------------------------------------------------

class Node(object):
    __slots__ = ("type", "literal", "destination", "title", "parent",
                 "first_child", "last_child", "prev", "next")

    def __init__(self, type_, literal=None):
        self.type = type_
        self.literal = literal
        self.destination = None
        self.title = None
        self.parent = None
        self.first_child = None
        self.last_child = None
        self.prev = None
        self.next = None

    def unlink(self):
        if self.prev is not None:
            self.prev.next = self.next
        elif self.parent is not None:
            self.parent.first_child = self.next
        if self.next is not None:
            self.next.prev = self.prev
        elif self.parent is not None:
            self.parent.last_child = self.prev
        self.parent = None
        self.next = None
        self.prev = None

    def append_child(self, child):
        child.unlink()
        child.parent = self
        if self.last_child is not None:
            self.last_child.next = child
            child.prev = self.last_child
            self.last_child = child
        else:
            self.first_child = child
            self.last_child = child

    def insert_after(self, sibling):
        sibling.unlink()
        sibling.next = self.next
        if sibling.next is not None:
            sibling.next.prev = sibling
        sibling.prev = self
        self.next = sibling
        sibling.parent = self.parent
        if sibling.next is None and sibling.parent is not None:
            sibling.parent.last_child = sibling

    def children(self):
        c = self.first_child
        while c is not None:
            nxt = c.next
            yield c
            c = nxt


class _Delimiter(object):
    __slots__ = ("cc", "numdelims", "origdelims", "node", "previous", "next",
                 "can_open", "can_close")


class _Bracket(object):
    __slots__ = ("node", "previous", "previous_delimiter", "index", "image",
                 "active", "bracket_after")


# ---------------------------------------------------------------------------
# Inline parser
# ---------------------------------------------------------------------------

class InlineParser(object):
    def __init__(self, refmap):
        self.refmap = refmap if refmap is not None else {}
        self.subject = ""
        self.pos = 0
        self.delimiters = None
        self.brackets = None
        self._missing = {}

    # -- utilities ---------------------------------------------------------

    def peek(self):
        if self.pos < len(self.subject):
            return self.subject[self.pos]
        return ""

    def _text(self, s):
        return Node("text", s)

    def spnl(self):
        self.pos = _SPNL_RE.match(self.subject, self.pos).end()

    # -- entry point -------------------------------------------------------

    def parse(self, text):
        root = Node("root")
        self.subject = text.strip(" \t\n")  # trailing/leading whitespace
        self.pos = 0
        self._missing = {}
        self.delimiters = None
        self.brackets = None
        n = len(self.subject)
        while self.pos < n:
            self.parse_inline(root)
        self.process_emphasis(None)
        _merge_text(root)
        return root

    def parse_inline(self, block):
        c = self.subject[self.pos]
        if c == "\n":
            self.handle_newline(block)
        elif c == "\\":
            self.handle_backslash(block)
        elif c == "`":
            self.handle_backticks(block)
        elif c == "*" or c == "_":
            self.handle_delim(c, block)
        elif c == "[":
            self.pos += 1
            node = self._text("[")
            block.append_child(node)
            self.add_bracket(node, self.pos - 1, False)
        elif c == "!":
            self.pos += 1
            if self.peek() == "[":
                self.pos += 1
                node = self._text("![")
                block.append_child(node)
                self.add_bracket(node, self.pos - 1, True)
            else:
                block.append_child(self._text("!"))
        elif c == "]":
            self.handle_close_bracket(block)
        elif c == "<":
            if not (self.handle_autolink(block) or self.handle_html_tag(block)):
                self.pos += 1
                block.append_child(self._text("<"))
        elif c == "&":
            m = _ENTITY_RE.match(self.subject, self.pos)
            d = _decode_entity(m.group(0)) if m else None
            if d is not None:
                self.pos = m.end()
                block.append_child(self._text(d))
            else:
                self.pos += 1
                block.append_child(self._text("&"))
        else:
            m = _TEXT_RE.match(self.subject, self.pos)
            if m is None:  # pragma: no cover - defensive
                self.pos += 1
                block.append_child(self._text(c))
            else:
                self.pos = m.end()
                block.append_child(self._text(m.group(0)))

    # -- individual constructs -------------------------------------------

    def handle_newline(self, block):
        self.pos += 1
        last = block.last_child
        if last is not None and last.type == "text" and last.literal.endswith(" "):
            stripped = last.literal.rstrip(" ")
            hard = len(last.literal) - len(stripped) >= 2
            last.literal = stripped
            block.append_child(Node("linebreak" if hard else "softbreak"))
        else:
            block.append_child(Node("softbreak"))
        # skip leading spaces on the next line
        n = len(self.subject)
        while self.pos < n and self.subject[self.pos] in " \t":
            self.pos += 1

    def handle_backslash(self, block):
        self.pos += 1
        c = self.peek()
        if c == "\n":
            self.pos += 1
            block.append_child(Node("linebreak"))
            n = len(self.subject)
            while self.pos < n and self.subject[self.pos] in " \t":
                self.pos += 1
        elif c and c in _ESCAPABLE_SET:
            self.pos += 1
            block.append_child(self._text(c))
        else:
            block.append_child(self._text("\\"))

    def handle_backticks(self, block):
        m = _TICKS_RE.match(self.subject, self.pos)
        ticks = m.group(0)
        after_open = m.end()
        search = after_open
        while True:
            m2 = _TICKS_RE.search(self.subject, search)
            if m2 is None:
                break
            if len(m2.group(0)) == len(ticks):
                contents = self.subject[after_open:m2.start()].replace("\n", " ")
                if (len(contents) > 0 and contents.strip(" ") != ""
                        and contents[0] == " " and contents[-1] == " "):
                    contents = contents[1:-1]
                block.append_child(Node("code", contents))
                self.pos = m2.end()
                return
            search = m2.end()
        self.pos = after_open
        block.append_child(self._text(ticks))

    def scan_delims(self, cc):
        s = self.subject
        start = self.pos
        i = start
        n = len(s)
        while i < n and s[i] == cc:
            i += 1
        numdelims = i - start
        char_before = s[start - 1] if start > 0 else "\n"
        char_after = s[i] if i < n else "\n"
        after_ws = _is_unicode_whitespace(char_after)
        after_punct = _is_unicode_punct(char_after)
        before_ws = _is_unicode_whitespace(char_before)
        before_punct = _is_unicode_punct(char_before)
        left = (not after_ws) and (not after_punct or before_ws or before_punct)
        right = (not before_ws) and (not before_punct or after_ws or after_punct)
        if cc == "_":
            can_open = left and (not right or before_punct)
            can_close = right and (not left or after_punct)
        else:
            can_open = left
            can_close = right
        return numdelims, can_open, can_close

    def handle_delim(self, cc, block):
        numdelims, can_open, can_close = self.scan_delims(cc)
        start = self.pos
        self.pos += numdelims
        node = self._text(self.subject[start:self.pos])
        block.append_child(node)
        if can_open or can_close:
            d = _Delimiter()
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
            key = (closer.cc, closer.can_open, closer.origdelims % 3)
            bottom = openers_bottom.get(key, stack_bottom)
            opener = closer.previous
            opener_found = False
            while opener is not None and opener is not stack_bottom and opener is not bottom:
                odd_match = ((closer.can_open or opener.can_close)
                             and closer.origdelims % 3 != 0
                             and (opener.origdelims + closer.origdelims) % 3 == 0)
                if opener.cc == closer.cc and opener.can_open and not odd_match:
                    opener_found = True
                    break
                opener = opener.previous
            old_closer = closer
            if not opener_found:
                closer = closer.next
            else:
                use = 2 if (closer.numdelims >= 2 and opener.numdelims >= 2) else 1
                opener_inl = opener.node
                closer_inl = closer.node
                opener.numdelims -= use
                closer.numdelims -= use
                opener_inl.literal = opener_inl.literal[:len(opener_inl.literal) - use]
                closer_inl.literal = closer_inl.literal[:len(closer_inl.literal) - use]
                emph = Node("emph" if use == 1 else "strong")
                tmp = opener_inl.next
                while tmp is not None and tmp is not closer_inl:
                    nxt = tmp.next
                    emph.append_child(tmp)
                    tmp = nxt
                opener_inl.insert_after(emph)
                # remove delimiters between opener and closer
                if opener.next is not closer:
                    opener.next = closer
                    closer.previous = opener
                if opener.numdelims == 0:
                    opener_inl.unlink()
                    self.remove_delimiter(opener)
                if closer.numdelims == 0:
                    closer_inl.unlink()
                    nxt = closer.next
                    self.remove_delimiter(closer)
                    closer = nxt
            if not opener_found:
                openers_bottom[key] = old_closer.previous
                if not old_closer.can_open:
                    self.remove_delimiter(old_closer)
        while self.delimiters is not None and self.delimiters is not stack_bottom:
            self.remove_delimiter(self.delimiters)

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

    def handle_close_bracket(self, block):
        self.pos += 1
        startpos = self.pos
        opener = self.brackets
        if opener is None:
            block.append_child(self._text("]"))
            return
        if not opener.active:
            block.append_child(self._text("]"))
            self.remove_bracket()
            return
        is_image = opener.image
        savepos = self.pos
        matched = False
        dest = None
        title = None
        s = self.subject

        # Inline link: [text](dest "title")
        if self.peek() == "(":
            self.pos += 1
            self.spnl()
            r = parse_link_destination(s, self.pos)
            ok = False
            if r is not None:
                dest = unescape_string(r[0])
                self.pos = r[1]
                before_title = self.pos
                self.spnl()
                if self.pos > 0 and s[self.pos - 1] in " \t\n" and self.pos != before_title:
                    t = parse_link_title(s, self.pos)
                    if t is not None:
                        title = unescape_string(t[0])
                        self.pos = t[1]
                    self.spnl()
                if self.peek() == ")":
                    self.pos += 1
                    ok = True
            if ok:
                matched = True
            else:
                self.pos = savepos
                dest = None
                title = None

        if not matched:
            # reference link
            beforelabel = self.pos
            r = parse_link_label(s, self.pos)
            reflabel = None
            n = 0
            if r is not None:
                n = r[1] - beforelabel
            if n > 2:
                reflabel = r[0]
                self.pos = r[1]
            elif not opener.bracket_after:
                # shortcut or collapsed reference: use the link text
                reflabel = s[opener.index + 1:startpos - 1]
                if n == 2:
                    self.pos = r[1]
            if n == 0:
                self.pos = savepos
            if reflabel is not None and len(reflabel) <= 999:
                key = normalize_label(reflabel)
                link = self.refmap.get(key) if key else None
                if link is not None:
                    dest = link["destination"]
                    title = link.get("title")
                    matched = True
            if not matched:
                self.pos = startpos

        if matched:
            node = Node("image" if is_image else "link")
            node.destination = dest
            node.title = title or ""
            tmp = opener.node.next
            while tmp is not None:
                nxt = tmp.next
                node.append_child(tmp)
                tmp = nxt
            block.append_child(node)
            self.process_emphasis(opener.previous_delimiter)
            self.remove_bracket()
            opener.node.unlink()
            if not is_image:
                o = self.brackets
                while o is not None:
                    if not o.image:
                        o.active = False
                    o = o.previous
        else:
            self.remove_bracket()
            self.pos = startpos
            block.append_child(self._text("]"))

    def handle_autolink(self, block):
        s = self.subject
        m = _EMAIL_RE.match(s, self.pos)
        if m is not None:
            addr = m.group(1)
            self.pos = m.end()
            node = Node("link")
            node.destination = "mailto:" + addr
            node.title = ""
            node.append_child(self._text(addr))
            block.append_child(node)
            return True
        m = _AUTOLINK_RE.match(s, self.pos)
        if m is not None:
            url = m.group(1)
            self.pos = m.end()
            node = Node("link")
            node.destination = url
            node.title = ""
            node.append_child(self._text(url))
            block.append_child(node)
            return True
        return False

    def _find_close(self, closer, start):
        """str.find with memo: once a closer is known to be absent from some
        position on, later searches fail immediately (avoids quadratic
        behaviour on inputs like many unclosed '<!--')."""
        missing = self._missing.get(closer)
        if missing is not None and start >= missing:
            return -1
        i = self.subject.find(closer, start)
        if i < 0:
            self._missing[closer] = start
        return i

    def handle_html_tag(self, block):
        s = self.subject
        pos = self.pos
        end = -1
        if s.startswith("<!--", pos):
            if s.startswith("<!-->", pos):
                end = pos + 5
            elif s.startswith("<!--->", pos):
                end = pos + 6
            else:
                i = self._find_close("-->", pos + 4)
                if i >= 0:
                    end = i + 3
        elif s.startswith("<?", pos):
            i = self._find_close("?>", pos + 2)
            if i >= 0:
                end = i + 2
        elif s.startswith("<![CDATA[", pos):
            i = self._find_close("]]>", pos + 9)
            if i >= 0:
                end = i + 3
        elif s.startswith("<!", pos):
            if pos + 2 < len(s) and s[pos + 2].isascii() and s[pos + 2].isalpha():
                i = self._find_close(">", pos + 3)
                if i >= 0:
                    end = i + 1
        else:
            m = _TAG_RE.match(s, pos)
            if m is not None:
                end = m.end()
        if end < 0:
            return False
        self.pos = end
        block.append_child(Node("html_inline", s[pos:end]))
        return True


def _walk(root):
    """Iterative pre/post-order walk yielding (node, entering) pairs for all
    descendants of root (no recursion, so deep nesting is safe)."""
    node = root.first_child
    if node is None:
        return
    while True:
        container = node.first_child is not None or node.type in _CONTAINERS
        yield node, True
        if container and node.first_child is not None:
            node = node.first_child
            continue
        if container:
            yield node, False
        while node.next is None:
            node = node.parent
            if node is root or node is None:
                return
            yield node, False
        node = node.next


_CONTAINERS = frozenset(("emph", "strong", "link", "image", "root"))


def _merge_text(root):
    """Merge adjacent text nodes (purely cosmetic; keeps the tree tidy)."""
    for node, entering in _walk(root):
        if entering and node.type == "text":
            nxt = node.next
            while nxt is not None and nxt.type == "text":
                node.literal += nxt.literal
                after = nxt.next
                nxt.unlink()
                nxt = after


# ---------------------------------------------------------------------------
# HTML rendering of inline nodes
# ---------------------------------------------------------------------------

def _render_tree(root, out):
    in_alt = 0  # > 0 while inside an image: render plain text only
    for c, entering in _walk(root):
        t = c.type
        if t == "text" or (t == "code" and in_alt):
            out.append(escape_html(c.literal))
        elif t == "softbreak":
            out.append("\n")
        elif t == "linebreak":
            out.append("\n" if in_alt else "<br />\n")
        elif t == "code":
            out.append("<code>" + escape_html(c.literal) + "</code>")
        elif t == "html_inline":
            out.append(c.literal)
        elif t == "image":
            if entering:
                if not in_alt:
                    out.append('<img src="' + escape_html(normalize_uri(c.destination)) + '" alt="')
                in_alt += 1
            else:
                in_alt -= 1
                if not in_alt:
                    out.append('"')
                    if c.title:
                        out.append(' title="' + escape_html(c.title) + '"')
                    out.append(" />")
        elif in_alt:
            continue
        elif t == "emph":
            out.append("<em>" if entering else "</em>")
        elif t == "strong":
            out.append("<strong>" if entering else "</strong>")
        elif t == "link":
            if entering:
                out.append('<a href="' + escape_html(normalize_uri(c.destination)) + '"')
                if c.title:
                    out.append(' title="' + escape_html(c.title) + '"')
                out.append(">")
            else:
                out.append("</a>")


def parse_inlines(text, refmap=None):
    """Parse inline content into a tree of Node objects (root node)."""
    return InlineParser(refmap).parse(text)


def render_inlines(text, refmap=None):
    """Parse and render inline content of a paragraph or heading to HTML."""
    root = parse_inlines(text, refmap)
    out = []
    _render_tree(root, out)
    return "".join(out)
