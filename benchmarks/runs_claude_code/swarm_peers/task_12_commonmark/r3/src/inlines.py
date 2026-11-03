"""Inline parsing for CommonMark 0.31.2.

Public API (see .swarm/board.md Decisions):
    render_inlines(text, refmap) -> str
    parse_inlines(text, refmap) -> Node (root of inline tree)
    normalize_label(label) -> str
    parse_link_label(s, pos) -> (inner_raw, newpos) | None
    parse_link_destination(s, pos) -> (dest_unescaped, newpos) | None
    parse_link_title(s, pos) -> (title_unescaped, newpos) | None
    unescape_string(s) -> str
    escape_html(s) -> str
    normalize_uri(s) -> str
"""

import re
import unicodedata
from html.entities import html5 as _HTML5

__all__ = [
    "render_inlines", "parse_inlines", "normalize_label", "parse_link_label",
    "parse_link_destination", "parse_link_title", "unescape_string",
    "escape_html", "normalize_uri", "decode_entity", "ASCII_PUNCT",
]

ASCII_PUNCT = "!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~"
_ESCAPABLE = set(ASCII_PUNCT)

_ENTITY_PAT = r"&(?:#[xX][0-9a-fA-F]{1,6}|#[0-9]{1,7}|[A-Za-z][A-Za-z0-9]{1,31});"
_RE_ENTITY = re.compile(_ENTITY_PAT)
_RE_ESC_OR_ENTITY = re.compile(r"\\([" + re.escape(ASCII_PUNCT) + r"])|(" + _ENTITY_PAT + ")")


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def escape_html(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;")
             .replace(">", "&gt;").replace('"', "&quot;"))


def decode_entity(ent):
    """Decode an entity/numeric reference like '&amp;' or '&#35;'.

    Returns the decoded string, or None if it is not a valid reference."""
    body = ent[1:-1]
    if body.startswith("#"):
        if body[1:2] in ("x", "X"):
            cp = int(body[2:], 16)
        else:
            cp = int(body[1:], 10)
        if cp == 0 or cp > 0x10FFFF or 0xD800 <= cp <= 0xDFFF:
            return "\uFFFD"
        return chr(cp)
    return _HTML5.get(body + ";")


def _unescape_repl(m):
    if m.group(1) is not None:
        return m.group(1)
    ent = m.group(2)
    dec = decode_entity(ent)
    return ent if dec is None else dec


def unescape_string(s):
    """Process backslash escapes and entity references."""
    if "\\" not in s and "&" not in s:
        return s
    return _RE_ESC_OR_ENTITY.sub(_unescape_repl, s)


_URI_SAFE = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
                ";/?:@&=+$,-_.!~*'()#")
_HEX = set("0123456789abcdefABCDEF")


def normalize_uri(s):
    """Percent-encode a URL the way the reference implementation does
    (existing %XX escapes are preserved)."""
    out = []
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        if c == "%" and i + 2 < n and s[i + 1] in _HEX and s[i + 2] in _HEX:
            out.append(s[i:i + 3])
            i += 3
            continue
        if c in _URI_SAFE:
            out.append(c)
        else:
            try:
                b = c.encode("utf-8")
            except UnicodeEncodeError:
                b = "\uFFFD".encode("utf-8")
            out.append("".join("%%%02X" % x for x in b))
        i += 1
    return "".join(out)


def normalize_label(label):
    """Normalize a link label (inner text, without brackets) for matching."""
    return re.sub(r"[ \t\r\n]+", " ", label.strip(" \t\r\n")).casefold()


def _is_unicode_ws(c):
    return c in "\t\n\x0c\r " or unicodedata.category(c) == "Zs"


def _is_unicode_punct(c):
    if c in _ESCAPABLE:
        return True
    cat = unicodedata.category(c)
    return cat[0] in ("P", "S")


# ---------------------------------------------------------------------------
# Link component parsers (shared with blocks.py)
# ---------------------------------------------------------------------------

def parse_link_label(s, pos):
    """s[pos] must be '['. Returns (inner_raw, pos_after_closing_bracket)
    or None. Does NOT check that the label contains non-whitespace."""
    if pos >= len(s) or s[pos] != "[":
        return None
    i = pos + 1
    n = len(s)
    while i < n:
        c = s[i]
        if c == "\\" and i + 1 < n:
            i += 2
            continue
        if c == "[":
            return None
        if c == "]":
            inner = s[pos + 1:i]
            if len(inner) > 999:
                return None
            return inner, i + 1
        i += 1
    return None


_RE_DEST_BRACES = re.compile(r"<((?:[^<>\n\\]|\\.)*)>", re.S)


def parse_link_destination(s, pos):
    """Returns (unescaped_destination, newpos) or None.

    A bare destination may be empty only if followed by ')'."""
    m = _RE_DEST_BRACES.match(s, pos)
    if m:
        return unescape_string(m.group(1)), m.end()
    n = len(s)
    if pos < n and s[pos] == "<":
        return None
    i = pos
    openparens = 0
    c = ""
    while i < n:
        c = s[i]
        if c == "\\" and i + 1 < n and s[i + 1] in _ESCAPABLE:
            i += 2
            continue
        if c == "(":
            openparens += 1
            i += 1
        elif c == ")":
            if openparens < 1:
                break
            openparens -= 1
            i += 1
        elif ord(c) <= 0x20 or ord(c) == 0x7F:
            break
        else:
            i += 1
    else:
        c = ""
    if i == pos and c != ")":
        return None
    if openparens != 0:
        return None
    return unescape_string(s[pos:i]), i


_RE_TITLE = re.compile(
    r'"((?:\\.|[^"\\])*)"|\'((?:\\.|[^\'\\])*)\'|\(((?:\\.|[^()\\])*)\)', re.S)


def parse_link_title(s, pos):
    m = _RE_TITLE.match(s, pos)
    if not m:
        return None
    raw = m.group(1)
    if raw is None:
        raw = m.group(2)
    if raw is None:
        raw = m.group(3)
    return unescape_string(raw), m.end()


# ---------------------------------------------------------------------------
# Inline node tree
# ---------------------------------------------------------------------------

class Node(object):
    __slots__ = ("type", "parent", "first_child", "last_child", "prev", "next",
                 "literal", "destination", "title")

    def __init__(self, type_, literal=None):
        self.type = type_
        self.parent = None
        self.first_child = None
        self.last_child = None
        self.prev = None
        self.next = None
        self.literal = literal
        self.destination = None
        self.title = None

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
            yield c
            c = c.next


class _Delim(object):
    __slots__ = ("cc", "numdelims", "origdelims", "node", "previous", "next",
                 "can_open", "can_close")


class _Bracket(object):
    __slots__ = ("node", "previous", "previous_delimiter", "index", "image",
                 "active", "bracket_after")


# ---------------------------------------------------------------------------
# Regexes for inline constructs
# ---------------------------------------------------------------------------

_RE_MAIN = re.compile(r"[^\n`\[\]\\!<&*_]+")
_RE_TICKS = re.compile(r"`+")
_RE_SPNL = re.compile(r"[ \t]*(?:\n[ \t]*)?")
_RE_AUTOLINK = re.compile(r"<([A-Za-z][A-Za-z0-9.+\-]{1,31}:[^<>\x00-\x20]*)>")
_RE_EMAIL = re.compile(
    r"<([a-zA-Z0-9.!#$%&'*+/=?^_`{|}~\-]+@[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?"
    r"(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*)>")

_TAGNAME = r"[A-Za-z][A-Za-z0-9\-]*"
_ATTRNAME = r"[a-zA-Z_:][a-zA-Z0-9_.:\-]*"
_UNQUOTED = r"[^\"'=<>`\x00-\x20]+"
_ATTRVALUE = r"(?:" + _UNQUOTED + r"|'[^']*'|\"[^\"]*\")"
_ATTRVALUESPEC = r"(?:[ \t\n\r\f\v]*=[ \t\n\r\f\v]*" + _ATTRVALUE + r")"
_ATTRIBUTE = r"(?:[ \t\n\r\f\v]+" + _ATTRNAME + _ATTRVALUESPEC + r"?)"
_OPENTAG = r"<" + _TAGNAME + _ATTRIBUTE + r"*[ \t\n\r\f\v]*/?>"
_CLOSETAG = r"</" + _TAGNAME + r"[ \t\n\r\f\v]*>"
_COMMENT = r"<!-->|<!--->|<!--[\s\S]*?-->"
_PI = r"<\?[\s\S]*?\?>"
_DECL = r"<![A-Za-z]+[^>]*>"
_CDATA = r"<!\[CDATA\[[\s\S]*?\]\]>"
_RE_HTML_TAG = re.compile(
    r"(?:" + _OPENTAG + "|" + _CLOSETAG + "|" + _COMMENT + "|" + _PI + "|"
    + _DECL + "|" + _CDATA + ")")


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

    # -- utilities ---------------------------------------------------------
    def peek(self):
        if self.pos < len(self.subject):
            return self.subject[self.pos]
        return None

    def match(self, regex):
        m = regex.match(self.subject, self.pos)
        if m is None:
            return None
        self.pos = m.end()
        return m.group(0)

    def spnl(self):
        self.match(_RE_SPNL)
        return True

    # -- entry point -------------------------------------------------------
    def parse(self, text):
        root = Node("root")
        self.subject = text
        self.pos = 0
        self.delimiters = None
        self.brackets = None
        n = len(text)
        while self.pos < n:
            self.parse_inline(root)
        self.process_emphasis(None)
        return root

    def parse_inline(self, block):
        c = self.subject[self.pos]
        res = False
        if c == "\n":
            res = self.parse_newline(block)
        elif c == "\\":
            res = self.parse_backslash(block)
        elif c == "`":
            res = self.parse_backticks(block)
        elif c == "*" or c == "_":
            res = self.handle_delim(c, block)
        elif c == "[":
            res = self.parse_open_bracket(block)
        elif c == "!":
            res = self.parse_bang(block)
        elif c == "]":
            res = self.parse_close_bracket(block)
        elif c == "<":
            res = self.parse_autolink(block) or self.parse_html_tag(block)
        elif c == "&":
            res = self.parse_entity(block)
        else:
            res = self.parse_string(block)
        if not res:
            self.pos += 1
            block.append_child(Node("text", c))
        return True

    # -- individual constructs ---------------------------------------------
    def parse_string(self, block):
        m = self.match(_RE_MAIN)
        if m is None:
            return False
        block.append_child(Node("text", m))
        return True

    def parse_newline(self, block):
        self.pos += 1
        last = block.last_child
        if last is not None and last.type == "text" and last.literal.endswith(" "):
            hard = last.literal.endswith("  ")
            last.literal = last.literal.rstrip(" ")
            block.append_child(Node("linebreak" if hard else "softbreak"))
        else:
            block.append_child(Node("softbreak"))
        # skip leading spaces/tabs on the next line
        n = len(self.subject)
        while self.pos < n and self.subject[self.pos] in " \t":
            self.pos += 1
        return True

    def parse_backslash(self, block):
        self.pos += 1
        c = self.peek()
        if c == "\n":
            self.pos += 1
            block.append_child(Node("linebreak"))
        elif c is not None and c in _ESCAPABLE:
            self.pos += 1
            block.append_child(Node("text", c))
        else:
            block.append_child(Node("text", "\\"))
        return True

    def parse_backticks(self, block):
        ticks = self.match(_RE_TICKS)
        if ticks is None:
            return False
        after_open = self.pos
        while True:
            m = _RE_TICKS.search(self.subject, self.pos)
            if m is None:
                break
            self.pos = m.end()
            if m.group(0) == ticks:
                contents = self.subject[after_open:m.start()].replace("\n", " ")
                if (len(contents) >= 2 and contents[0] == " " and contents[-1] == " "
                        and contents.strip(" ") != ""):
                    contents = contents[1:-1]
                block.append_child(Node("code", contents))
                return True
        self.pos = after_open
        block.append_child(Node("text", ticks))
        return True

    def parse_autolink(self, block):
        m = _RE_EMAIL.match(self.subject, self.pos)
        if m:
            self.pos = m.end()
            addr = m.group(1)
            node = Node("link")
            node.destination = "mailto:" + addr
            node.title = ""
            node.append_child(Node("text", addr))
            block.append_child(node)
            return True
        m = _RE_AUTOLINK.match(self.subject, self.pos)
        if m:
            self.pos = m.end()
            uri = m.group(1)
            node = Node("link")
            node.destination = uri
            node.title = ""
            node.append_child(Node("text", uri))
            block.append_child(node)
            return True
        return False

    def parse_html_tag(self, block):
        m = _RE_HTML_TAG.match(self.subject, self.pos)
        if m is None:
            return False
        self.pos = m.end()
        block.append_child(Node("html_inline", m.group(0)))
        return True

    def parse_entity(self, block):
        m = _RE_ENTITY.match(self.subject, self.pos)
        if m is None:
            return False
        dec = decode_entity(m.group(0))
        if dec is None:
            return False
        self.pos = m.end()
        block.append_child(Node("text", dec))
        return True

    # -- emphasis ----------------------------------------------------------
    def scan_delims(self, cc):
        startpos = self.pos
        n = len(self.subject)
        i = startpos
        while i < n and self.subject[i] == cc:
            i += 1
        numdelims = i - startpos
        if numdelims == 0:
            return None
        char_before = self.subject[startpos - 1] if startpos > 0 else "\n"
        char_after = self.subject[i] if i < n else "\n"
        after_ws = _is_unicode_ws(char_after)
        after_punct = _is_unicode_punct(char_after)
        before_ws = _is_unicode_ws(char_before)
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
        res = self.scan_delims(cc)
        if res is None:
            return False
        numdelims, can_open, can_close = res
        startpos = self.pos
        self.pos += numdelims
        node = Node("text", self.subject[startpos:self.pos])
        block.append_child(node)
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
        return True

    def remove_delimiter(self, delim):
        if delim.previous is not None:
            delim.previous.next = delim.next
        if delim.next is None:
            self.delimiters = delim.previous
        else:
            delim.next.previous = delim.previous

    @staticmethod
    def remove_delimiters_between(bottom, top):
        if bottom.next is not top:
            bottom.next = top
            top.previous = bottom

    def process_emphasis(self, stack_bottom):
        openers_bottom = {}
        closer = self.delimiters
        while closer is not None and closer.previous is not stack_bottom:
            closer = closer.previous
        while closer is not None:
            if not closer.can_close:
                closer = closer.next
                continue
            closercc = closer.cc
            key = (closercc, closer.can_open, closer.origdelims % 3)
            bottom = openers_bottom.get(key, stack_bottom)
            opener = closer.previous
            opener_found = False
            while (opener is not None and opener is not stack_bottom
                   and opener is not bottom):
                odd_match = ((closer.can_open or opener.can_close)
                             and closer.origdelims % 3 != 0
                             and (opener.origdelims + closer.origdelims) % 3 == 0)
                if opener.cc == closercc and opener.can_open and not odd_match:
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
                    tmp.unlink()
                    emph.append_child(tmp)
                    tmp = nxt
                opener_inl.insert_after(emph)
                self.remove_delimiters_between(opener, closer)
                if opener.numdelims == 0:
                    opener_inl.unlink()
                    self.remove_delimiter(opener)
                if closer.numdelims == 0:
                    closer_inl.unlink()
                    tempstack = closer.next
                    self.remove_delimiter(closer)
                    closer = tempstack
            if not opener_found:
                openers_bottom[key] = old_closer.previous
                if not old_closer.can_open:
                    self.remove_delimiter(old_closer)
        while self.delimiters is not None and self.delimiters is not stack_bottom:
            self.remove_delimiter(self.delimiters)

    # -- links and images --------------------------------------------------
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

    def parse_open_bracket(self, block):
        startpos = self.pos
        self.pos += 1
        node = Node("text", "[")
        block.append_child(node)
        self.add_bracket(node, startpos, False)
        return True

    def parse_bang(self, block):
        startpos = self.pos
        self.pos += 1
        if self.peek() == "[":
            self.pos += 1
            node = Node("text", "![")
            block.append_child(node)
            self.add_bracket(node, startpos + 1, True)
        else:
            block.append_child(Node("text", "!"))
        return True

    def parse_close_bracket(self, block):
        startpos = self.pos
        self.pos += 1
        opener = self.brackets
        if opener is None:
            block.append_child(Node("text", "]"))
            return True
        if not opener.active:
            block.append_child(Node("text", "]"))
            self.remove_bracket()
            return True
        is_image = opener.image
        savepos = self.pos
        matched = False
        dest = None
        title = None

        # inline link?
        if self.peek() == "(":
            self.pos += 1
            self.spnl()
            r = parse_link_destination(self.subject, self.pos)
            ok = False
            if r is not None:
                dest, self.pos = r
                self.spnl()
                if self.subject[self.pos - 1] in " \t\n":
                    t = parse_link_title(self.subject, self.pos)
                    if t is not None:
                        title, self.pos = t
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
            beforelabel = self.pos
            reflabel = None
            r = parse_link_label(self.subject, beforelabel)
            n = 0
            if r is not None:
                n = r[1] - beforelabel
            if n > 2:
                reflabel = r[0]
                self.pos = r[1]
            elif not opener.bracket_after:
                # collapsed ([]) or shortcut reference: use the link text
                reflabel = self.subject[opener.index + 1:startpos]
                if n == 2:
                    self.pos = r[1]
            if n == 0:
                self.pos = savepos
            if reflabel is not None:
                link = self.refmap.get(normalize_label(reflabel))
                if link is not None:
                    dest, title = link[0], link[1]
                    matched = True

        if matched:
            node = Node("image" if is_image else "link")
            node.destination = dest
            node.title = title or ""
            tmp = opener.node.next
            while tmp is not None:
                nxt = tmp.next
                tmp.unlink()
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
            return True

        self.remove_bracket()
        self.pos = startpos + 1
        block.append_child(Node("text", "]"))
        return True


# ---------------------------------------------------------------------------
# HTML rendering of inline trees
# ---------------------------------------------------------------------------

def _walk(root):
    """Iterative pre/post-order walk yielding (node, entering)."""
    stack = []
    c = root.first_child
    while True:
        if c is not None:
            yield c, True
            if c.first_child is not None:
                stack.append(c)
                c = c.first_child
                continue
            yield c, False
            c = c.next
        else:
            if not stack:
                return
            c = stack.pop()
            yield c, False
            c = c.next


def _render_alt(node, out):
    for c, entering in _walk(node):
        if not entering:
            continue
        t = c.type
        if t == "text" or t == "code":
            out.append(escape_html(c.literal))
        elif t == "html_inline":
            out.append(c.literal)
        elif t == "softbreak" or t == "linebreak":
            out.append("\n")


def _render_nodes(root, out):
    image_depth = 0
    for c, entering in _walk(root):
        t = c.type
        if image_depth > 0:
            # inside an image: only plain text goes into the alt attribute
            if t == "image":
                if entering:
                    image_depth += 1
                else:
                    image_depth -= 1
                    if image_depth == 0:
                        out.append('"')
                        if c.title:
                            out.append(' title="' + escape_html(c.title) + '"')
                        out.append(" />")
            elif entering:
                if t == "text" or t == "code":
                    out.append(escape_html(c.literal))
                elif t == "html_inline":
                    out.append(c.literal)
                elif t == "softbreak" or t == "linebreak":
                    out.append("\n")
            continue
        if t == "text":
            if entering:
                out.append(escape_html(c.literal))
        elif t == "softbreak":
            if entering:
                out.append("\n")
        elif t == "linebreak":
            if entering:
                out.append("<br />\n")
        elif t == "code":
            if entering:
                out.append("<code>" + escape_html(c.literal) + "</code>")
        elif t == "html_inline":
            if entering:
                out.append(c.literal)
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
        elif t == "image":
            if entering:
                out.append('<img src="' + escape_html(normalize_uri(c.destination))
                           + '" alt="')
                image_depth = 1
            else:  # image without children
                out.append('"')
                if c.title:
                    out.append(' title="' + escape_html(c.title) + '"')
                out.append(" />")


def parse_inlines(text, refmap=None):
    """Parse inline content into a Node tree (root type 'root')."""
    text = text.strip(" \t\n")
    return InlineParser(refmap).parse(text)


def render_inlines(text, refmap=None):
    """Parse inline content and render it to HTML."""
    root = parse_inlines(text, refmap)
    out = []
    _render_nodes(root, out)
    return "".join(out)
