"""Inline parsing for CommonMark 0.31.2.

Handles code spans, emphasis, links and images (inline, reference,
collapsed, shortcut), autolinks, raw HTML, hard/soft line breaks,
backslash escapes and entity / numeric character references.
"""

import re
import string
import unicodedata
from html.entities import html5

from .node import Node

# ---------------------------------------------------------------------------
# Shared regular expressions
# ---------------------------------------------------------------------------

ESCAPABLE = r"[!\"#$%&'()*+,./:;<=>?@\[\\\]^_`{|}~-]"
ENTITY = r'&(?:#[xX][0-9a-fA-F]{1,6}|#[0-9]{1,7}|[A-Za-z][A-Za-z0-9]{1,31});'

# whitespace: spaces/tabs with at most one line ending
_WS_OPT = r'[ \t]*(?:\n[ \t]*)?'
_WS_REQ = r'(?:[ \t]+(?:\n[ \t]*)?|\n[ \t]*)'

TAGNAME = r'[A-Za-z][A-Za-z0-9-]*'
ATTRIBUTENAME = r'[A-Za-z_:][A-Za-z0-9_.:-]*'
UNQUOTEDVALUE = r'[^"\'=<>`\x00-\x20]+'
SINGLEQUOTEDVALUE = r"'[^']*'"
DOUBLEQUOTEDVALUE = r'"[^"]*"'
ATTRIBUTEVALUE = '(?:' + UNQUOTEDVALUE + '|' + SINGLEQUOTEDVALUE + '|' + DOUBLEQUOTEDVALUE + ')'
ATTRIBUTEVALUESPEC = '(?:' + _WS_OPT + '=' + _WS_OPT + ATTRIBUTEVALUE + ')'
ATTRIBUTE = '(?:' + _WS_REQ + ATTRIBUTENAME + ATTRIBUTEVALUESPEC + '?)'
OPENTAG = '<' + TAGNAME + ATTRIBUTE + '*' + _WS_OPT + '/?>'
CLOSETAG = '</' + TAGNAME + _WS_OPT + '>'
HTMLCOMMENT = r'<!---?>|<!--[\s\S]*?-->'
PROCESSINGINSTRUCTION = r'<\?[\s\S]*?\?>'
DECLARATION = r'<![A-Za-z][^>]*>'
CDATA = r'<!\[CDATA\[[\s\S]*?\]\]>'
HTMLTAG = ('(?:' + OPENTAG + '|' + CLOSETAG + '|' + HTMLCOMMENT + '|' +
           PROCESSINGINSTRUCTION + '|' + DECLARATION + '|' + CDATA + ')')

reHtmlTag = re.compile(HTMLTAG)
reEntityOrEscapedChar = re.compile(r'\\' + ESCAPABLE + '|' + ENTITY)
reEscapable = re.compile(ESCAPABLE)
reEntityHere = re.compile(ENTITY)
reTicks = re.compile(r'`+')
reTicksHere = re.compile(r'`+')
reLinkTitle = re.compile(
    r'"(?:\\[\s\S]|[^\\"\x00])*"'
    r"|'(?:\\[\s\S]|[^\\'\x00])*'"
    r'|\((?:\\[\s\S]|[^\\()\x00])*\)')
reLinkDestinationBraces = re.compile(r'<(?:[^<>\n\\\x00]|\\.)*>')
reEmailAutolink = re.compile(
    r"<([a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9]"
    r"(?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?"
    r"(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*)>")
reAutolink = re.compile(r'<[A-Za-z][A-Za-z0-9.+-]{1,31}:[^<>\x00-\x20]*>')
reSpnl = re.compile(r'[ \t]*(?:\n[ \t]*)?')
reFinalSpace = re.compile(r' *$')
reInitialSpace = re.compile(r'[ \t]*')
reSpaceAtEndOfLine = re.compile(r'[ \t]*(?:\n|$)')
reLinkLabel = re.compile(r'\[(?:[^\\\[\]]|\\[\s\S]){0,1000}\]')
reMain = re.compile(r'[^\n`\[\]\\!<&*_]+')
reWhitespaceRun = re.compile(r'[ \t\r\n]+')

# Same nesting limit for unbracketed link destinations as the reference
# implementation (keeps pathological input linear).
MAX_LINK_PAREN_DEPTH = 32

_URI_SAFE =frozenset(";/?:@&=+$,-_.!~*'()#" + string.ascii_letters + string.digits)
_HEX = frozenset(string.hexdigits)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def decode_entity(s):
    """Decode an entity or numeric character reference (``&...;``)."""
    body = s[1:-1]
    if body.startswith('#'):
        if body[1:2] in ('x', 'X'):
            cp = int(body[2:], 16)
        else:
            cp = int(body[1:])
        if cp == 0 or cp > 0x10FFFF or 0xD800 <= cp <= 0xDFFF:
            return '�'
        return chr(cp)
    value = html5.get(body + ';')
    return value if value is not None else s


def _unescape_match(m):
    s = m.group(0)
    if s[0] == '\\':
        return s[1]
    return decode_entity(s)


def unescape_string(s):
    """Process backslash escapes and entity references in ``s``."""
    if '\\' in s or '&' in s:
        return reEntityOrEscapedChar.sub(_unescape_match, s)
    return s


def normalize_uri(uri):
    """Percent-encode a link destination (keeping existing %XX escapes)."""
    out = []
    i = 0
    n = len(uri)
    while i < n:
        c = uri[i]
        if c == '%' and i + 2 < n and uri[i + 1] in _HEX and uri[i + 2] in _HEX:
            out.append(uri[i:i + 3])
            i += 3
            continue
        if c in _URI_SAFE:
            out.append(c)
        else:
            for b in c.encode('utf-8', 'surrogatepass'):
                out.append('%%%02X' % b)
        i += 1
    return ''.join(out)


def normalize_reference(label):
    """Normalize a link label (including its surrounding brackets)."""
    inner = label[1:-1].strip(' \t\r\n')
    return reWhitespaceRun.sub(' ', inner).casefold()


def is_unicode_whitespace(c):
    return c in '\t\n\x0c\r' or unicodedata.category(c) == 'Zs'


def is_punctuation(c):
    return unicodedata.category(c)[0] in ('P', 'S')


def _text(s):
    return Node('text', s)


class _Delimiter:
    __slots__ = ('cc', 'numdelims', 'origdelims', 'node', 'previous', 'next',
                 'can_open', 'can_close')

    def __init__(self, cc, numdelims, node, previous, can_open, can_close):
        self.cc = cc
        self.numdelims = numdelims
        self.origdelims = numdelims
        self.node = node
        self.previous = previous
        self.next = None
        self.can_open = can_open
        self.can_close = can_close


class _Bracket:
    __slots__ = ('node', 'previous', 'previous_delimiter', 'index', 'image',
                 'active', 'bracket_after')

    def __init__(self, node, previous, previous_delimiter, index, image):
        self.node = node
        self.previous = previous
        self.previous_delimiter = previous_delimiter
        self.index = index
        self.image = image
        self.active = True
        self.bracket_after = False


# ---------------------------------------------------------------------------
# Inline parser
# ---------------------------------------------------------------------------

class InlineParser:
    def __init__(self):
        self.subject = ''
        self.pos = 0
        self.delimiters = None
        self.brackets = None
        self.refmap = {}

    # -- low level -------------------------------------------------------
    def match(self, regex):
        m = regex.match(self.subject, self.pos)
        if m is None:
            return None
        self.pos = m.end()
        return m.group(0)

    def search(self, regex):
        m = regex.search(self.subject, self.pos)
        if m is None:
            return None
        self.pos = m.end()
        return m.group(0)

    def peek(self):
        if self.pos < len(self.subject):
            return self.subject[self.pos]
        return None

    def spnl(self):
        self.match(reSpnl)
        return True

    # -- entry point -----------------------------------------------------
    def parse(self, block):
        self.subject = block.string_content.strip(' \t\r\n')
        self.pos = 0
        self.delimiters = None
        self.brackets = None
        while self.parse_inline(block):
            pass
        block.string_content = None
        self.process_emphasis(None)

    def parse_inline(self, block):
        c = self.peek()
        if c is None:
            return False
        if c == '\n':
            res = self.parse_newline(block)
        elif c == '\\':
            res = self.parse_backslash(block)
        elif c == '`':
            res = self.parse_backticks(block)
        elif c == '*' or c == '_':
            res = self.handle_delim(c, block)
        elif c == '[':
            res = self.parse_open_bracket(block)
        elif c == '!':
            res = self.parse_bang(block)
        elif c == ']':
            res = self.parse_close_bracket(block)
        elif c == '<':
            res = self.parse_autolink(block) or self.parse_html_tag(block)
        elif c == '&':
            res = self.parse_entity(block)
        else:
            res = self.parse_string(block)
        if not res:
            self.pos += 1
            block.append_child(_text(c))
        return True

    # -- individual constructs -------------------------------------------
    def parse_newline(self, block):
        self.pos += 1
        lastc = block.last_child
        if lastc is not None and lastc.type == 'text' and lastc.literal.endswith(' '):
            hardbreak = lastc.literal.endswith('  ')
            lastc.literal = reFinalSpace.sub('', lastc.literal)
            block.append_child(Node('linebreak' if hardbreak else 'softbreak'))
        else:
            block.append_child(Node('softbreak'))
        self.match(reInitialSpace)
        return True

    def parse_backslash(self, block):
        subj = self.subject
        self.pos += 1
        c = self.peek()
        if c == '\n':
            self.pos += 1
            block.append_child(Node('linebreak'))
            self.match(reInitialSpace)
        elif c is not None and reEscapable.match(c):
            block.append_child(_text(c))
            self.pos += 1
        else:
            block.append_child(_text('\\'))
        return True

    def parse_backticks(self, block):
        ticks = self.match(reTicksHere)
        if ticks is None:
            return False
        after_open = self.pos
        while True:
            m = reTicks.search(self.subject, self.pos)
            if m is None:
                break
            self.pos = m.end()
            if m.group(0) == ticks:
                contents = self.subject[after_open:m.start()].replace('\n', ' ')
                if (len(contents) > 0 and contents.strip(' ') != '' and
                        contents[0] == ' ' and contents[-1] == ' '):
                    contents = contents[1:-1]
                block.append_child(Node('code', contents))
                return True
        self.pos = after_open
        block.append_child(_text(ticks))
        return True

    def scan_delims(self, cc):
        startpos = self.pos
        numdelims = 0
        while self.peek() == cc:
            numdelims += 1
            self.pos += 1
        if numdelims == 0:
            return None
        char_before = '\n' if startpos == 0 else self.subject[startpos - 1]
        c_after = self.peek()
        char_after = '\n' if c_after is None else c_after
        after_ws = is_unicode_whitespace(char_after)
        after_p = is_punctuation(char_after)
        before_ws = is_unicode_whitespace(char_before)
        before_p = is_punctuation(char_before)
        left = not after_ws and (not after_p or before_ws or before_p)
        right = not before_ws and (not before_p or after_ws or after_p)
        if cc == '_':
            can_open = left and (not right or before_p)
            can_close = right and (not left or after_p)
        else:
            can_open = left
            can_close = right
        self.pos = startpos
        return numdelims, can_open, can_close

    def handle_delim(self, cc, block):
        res = self.scan_delims(cc)
        if res is None:
            return False
        numdelims, can_open, can_close = res
        startpos = self.pos
        self.pos += numdelims
        node = _text(self.subject[startpos:self.pos])
        block.append_child(node)
        if can_open or can_close:
            d = _Delimiter(cc, numdelims, node, self.delimiters, can_open, can_close)
            if d.previous is not None:
                d.previous.next = d
            self.delimiters = d
        return True

    def remove_delimiter(self, delim):
        if delim.previous is not None:
            delim.previous.next = delim.next
        if delim.next is not None:
            delim.next.previous = delim.previous
        else:
            self.delimiters = delim.previous

    @staticmethod
    def remove_delimiters_between(bottom, top):
        if bottom.next is not top:
            bottom.next = top
            top.previous = bottom

    def process_emphasis(self, stack_bottom):
        openers_bottom = [stack_bottom] * 14
        closer = self.delimiters
        while closer is not None and closer.previous is not stack_bottom:
            closer = closer.previous
        while closer is not None:
            if not closer.can_close:
                closer = closer.next
                continue
            opener = closer.previous
            opener_found = False
            base = 2 if closer.cc == '_' else 8
            idx = base + (3 if closer.can_open else 0) + (closer.origdelims % 3)
            while (opener is not None and opener is not stack_bottom and
                   opener is not openers_bottom[idx]):
                odd_match = ((closer.can_open or opener.can_close) and
                             closer.origdelims % 3 != 0 and
                             (opener.origdelims + closer.origdelims) % 3 == 0)
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
                emph = Node('emph' if use == 1 else 'strong')
                tmp = opener_inl.next
                while tmp is not None and tmp is not closer_inl:
                    nxt = tmp.next
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
                openers_bottom[idx] = old_closer.previous
                if not old_closer.can_open:
                    self.remove_delimiter(old_closer)
        while self.delimiters is not None and self.delimiters is not stack_bottom:
            self.remove_delimiter(self.delimiters)

    # -- links -------------------------------------------------------------
    def parse_link_title(self):
        title = self.match(reLinkTitle)
        if title is None:
            return None
        return unescape_string(title[1:-1])

    def parse_link_destination(self):
        res = self.match(reLinkDestinationBraces)
        if res is not None:
            return normalize_uri(unescape_string(res[1:-1]))
        if self.peek() == '<':
            return None
        savepos = self.pos
        openparens = 0
        subj = self.subject
        n = len(subj)
        c = None
        while self.pos < n:
            c = subj[self.pos]
            if c == '\\' and self.pos + 1 < n and reEscapable.match(subj[self.pos + 1]):
                self.pos += 2
            elif c == '(':
                self.pos += 1
                openparens += 1
                if openparens > MAX_LINK_PAREN_DEPTH:
                    self.pos = savepos
                    return None
            elif c == ')':
                if openparens < 1:
                    break
                self.pos += 1
                openparens -= 1
            elif c in ' \t\n\x0b\x0c\r' or ord(c) < 0x20 or ord(c) == 0x7f:
                break
            else:
                self.pos += 1
        if self.pos == savepos and c != ')':
            return None
        if openparens != 0:
            self.pos = savepos
            return None
        res = subj[savepos:self.pos]
        return normalize_uri(unescape_string(res))

    def parse_link_label(self):
        m = self.match(reLinkLabel)
        if m is None or len(m) > 1001:
            return 0
        return len(m)

    def add_bracket(self, node, index, image):
        if self.brackets is not None:
            self.brackets.bracket_after = True
        self.brackets = _Bracket(node, self.brackets, self.delimiters, index, image)

    def remove_bracket(self):
        self.brackets = self.brackets.previous

    def parse_open_bracket(self, block):
        startpos = self.pos
        self.pos += 1
        node = _text('[')
        block.append_child(node)
        self.add_bracket(node, startpos, False)
        return True

    def parse_bang(self, block):
        startpos = self.pos
        self.pos += 1
        if self.peek() == '[':
            self.pos += 1
            node = _text('![')
            block.append_child(node)
            self.add_bracket(node, startpos + 1, True)
        else:
            block.append_child(_text('!'))
        return True

    def parse_close_bracket(self, block):
        self.pos += 1
        startpos = self.pos
        opener = self.brackets
        if opener is None:
            block.append_child(_text(']'))
            return True
        if not opener.active:
            block.append_child(_text(']'))
            self.remove_bracket()
            return True
        is_image = opener.image
        savepos = self.pos
        matched = False
        dest = None
        title = None

        if self.peek() == '(':
            self.pos += 1
            ok = False
            self.spnl()
            dest = self.parse_link_destination()
            if dest is not None:
                self.spnl()
                if self.pos > 0 and self.subject[self.pos - 1] in ' \t\n':
                    title = self.parse_link_title()
                self.spnl()
                if self.peek() == ')':
                    self.pos += 1
                    ok = True
            if ok:
                matched = True
            else:
                self.pos = savepos
                title = None

        if not matched:
            beforelabel = self.pos
            n = self.parse_link_label()
            reflabel = None
            if n > 2:
                reflabel = self.subject[beforelabel:beforelabel + n]
            elif not opener.bracket_after:
                reflabel = self.subject[opener.index:startpos]
            if n == 0:
                self.pos = savepos
            if reflabel:
                link = self.refmap.get(normalize_reference(reflabel))
                if link is not None:
                    dest, title = link
                    matched = True

        if matched:
            node = Node('image' if is_image else 'link')
            node.destination = dest
            node.title = title or ''
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
            return True

        self.remove_bracket()
        self.pos = startpos
        block.append_child(_text(']'))
        return True

    def parse_autolink(self, block):
        m = self.match(reEmailAutolink)
        if m is not None:
            dest = m[1:-1]
            node = Node('link')
            node.destination = normalize_uri('mailto:' + dest)
            node.title = ''
            node.append_child(_text(dest))
            block.append_child(node)
            return True
        m = self.match(reAutolink)
        if m is not None:
            dest = m[1:-1]
            node = Node('link')
            node.destination = normalize_uri(dest)
            node.title = ''
            node.append_child(_text(dest))
            block.append_child(node)
            return True
        return False

    def parse_html_tag(self, block):
        m = self.match(reHtmlTag)
        if m is None:
            return False
        block.append_child(Node('html_inline', m))
        return True

    def parse_entity(self, block):
        m = self.match(reEntityHere)
        if m is None:
            return False
        block.append_child(_text(decode_entity(m)))
        return True

    def parse_string(self, block):
        m = self.match(reMain)
        if m is None:
            return False
        block.append_child(_text(m))
        return True

    # -- link reference definitions -----------------------------------------
    def parse_reference(self, s, refmap):
        """Try to parse a link reference definition at the start of ``s``.

        Returns the number of characters consumed (0 on failure).
        """
        self.subject = s
        self.pos = 0
        startpos = 0

        n = self.parse_link_label()
        if n == 0:
            return 0
        rawlabel = s[:n]

        if self.peek() == ':':
            self.pos += 1
        else:
            self.pos = startpos
            return 0

        self.spnl()
        dest = self.parse_link_destination()
        if dest is None:
            self.pos = startpos
            return 0

        beforetitle = self.pos
        self.spnl()
        title = None
        if self.pos != beforetitle:
            title = self.parse_link_title()
        if title is None:
            self.pos = beforetitle

        at_line_end = True
        if self.match(reSpaceAtEndOfLine) is None:
            if title is None:
                at_line_end = False
            else:
                title = None
                self.pos = beforetitle
                at_line_end = self.match(reSpaceAtEndOfLine) is not None
        if not at_line_end:
            self.pos = startpos
            return 0

        normlabel = normalize_reference(rawlabel)
        if normlabel == '':
            self.pos = startpos
            return 0
        if normlabel not in refmap:
            refmap[normlabel] = (dest, title if title is not None else '')
        return self.pos - startpos
