"""Inline parsing for CommonMark 0.31.2.

Handles code spans, emphasis and strong emphasis (delimiter-run algorithm),
links and images (inline, full/collapsed/shortcut reference), autolinks,
raw HTML, hard and soft line breaks, backslash escapes and entity /
numeric character references. Also parses link reference definitions on
behalf of the block parser.
"""

import re
import unicodedata
from html.entities import html5

from .node import Node

# ---------------------------------------------------------------------------
# Shared patterns
# ---------------------------------------------------------------------------

ESCAPABLE = r'[!"#$%&\'()*+,./:;<=>?@\[\\\]^_`{|}~-]'
ENTITY = r'&(?:#[xX][0-9a-fA-F]{1,6}|#[0-9]{1,7}|[A-Za-z][A-Za-z0-9]{1,31});'

_WS = r'[ \t\n]'
TAGNAME = r'[A-Za-z][A-Za-z0-9-]*'
ATTRIBUTENAME = r'[a-zA-Z_:][a-zA-Z0-9_.:-]*'
UNQUOTEDVALUE = r'[^"\'=<>`\x00-\x20]+'
SINGLEQUOTEDVALUE = r"'[^']*'"
DOUBLEQUOTEDVALUE = r'"[^"]*"'
ATTRIBUTEVALUE = ('(?:' + UNQUOTEDVALUE + '|' + SINGLEQUOTEDVALUE + '|'
                  + DOUBLEQUOTEDVALUE + ')')
ATTRIBUTEVALUESPEC = '(?:' + _WS + '*=' + _WS + '*' + ATTRIBUTEVALUE + ')'
ATTRIBUTE = '(?:' + _WS + '+' + ATTRIBUTENAME + ATTRIBUTEVALUESPEC + '?)'
OPENTAG = '<' + TAGNAME + ATTRIBUTE + '*' + _WS + '*/?>'
CLOSETAG = '</' + TAGNAME + _WS + '*>'
HTMLCOMMENT = r'<!-->|<!--->|<!--[\s\S]*?-->'
PROCESSINGINSTRUCTION = r'<\?[\s\S]*?\?>'
DECLARATION = r'<![A-Za-z][^>]*>'
CDATA = r'<!\[CDATA\[[\s\S]*?\]\]>'
HTMLTAG = ('(?:' + OPENTAG + '|' + CLOSETAG + '|' + HTMLCOMMENT + '|'
           + PROCESSINGINSTRUCTION + '|' + DECLARATION + '|' + CDATA + ')')

RE_HTML_TAG = re.compile(HTMLTAG)
RE_OPEN_OR_CLOSE_TAG = re.compile('(?:' + OPENTAG + '|' + CLOSETAG + ')')
RE_ENTITY_HERE = re.compile(ENTITY)
RE_ENTITY_OR_ESCAPED = re.compile(r'\\' + ESCAPABLE + '|' + ENTITY)
RE_ESCAPABLE = re.compile(ESCAPABLE)
RE_MAIN = re.compile(r'[^\n`\[\]\\!<&*_]+')
RE_TICKS_HERE = re.compile(r'`+')
RE_TICKS = re.compile(r'`+')
RE_SPNL = re.compile(r'[ \t]*(?:\n[ \t]*)?')
RE_SPACE_AT_END_OF_LINE = re.compile(r'[ \t]*(?:\n|$)')
RE_INITIAL_SPACE = re.compile(r'[ \t]*')
RE_LINK_LABEL = re.compile(r'\[(?:[^\\\[\]]|\\.){0,1000}\]', re.S)
RE_LINK_DEST_BRACES = re.compile(r'<(?:[^<>\n\\]|\\.)*>')
RE_LINK_TITLE = re.compile(
    r'"(?:\\.|[^"\\])*"' + '|' + r"'(?:\\.|[^'\\])*'" + '|'
    + r'\((?:\\.|[^()\\])*\)', re.S)
RE_EMAIL_AUTOLINK = re.compile(
    r"<([a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9]"
    r"(?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?"
    r"(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*)>")
RE_AUTOLINK = re.compile(r'<[A-Za-z][A-Za-z0-9.+-]{1,31}:[^<>\x00-\x20]*>')
RE_LABEL_WS = re.compile(r'[ \t\r\n]+')


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def decode_entity(ent):
    """Decode an entity or numeric character reference (with & and ;)."""
    if ent[1] == '#':
        if ent[2] in 'xX':
            cp = int(ent[3:-1], 16)
        else:
            cp = int(ent[2:-1], 10)
        if cp == 0 or cp > 0x10FFFF or 0xD800 <= cp <= 0xDFFF:
            return '�'
        return chr(cp)
    value = html5.get(ent[1:-1] + ';')
    if value is None:
        return ent
    return value


def _unescape_match(m):
    s = m.group(0)
    if s[0] == '\\':
        return s[1]
    return decode_entity(s)


def unescape_string(s):
    """Process backslash escapes and entity references in a string."""
    if '\\' not in s and '&' not in s:
        return s
    return RE_ENTITY_OR_ESCAPED.sub(_unescape_match, s)


_URL_SAFE = frozenset(
    'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
    ";/?:@&=+$,-_.!~*'()#")
_HEX = frozenset('0123456789abcdefABCDEF')
_ASCII_LETTERS = frozenset('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz')


def normalize_uri(uri):
    """Percent-encode a link destination, keeping existing %XX escapes."""
    out = []
    i = 0
    n = len(uri)
    while i < n:
        c = uri[i]
        if c == '%' and i + 2 < n and uri[i + 1] in _HEX and uri[i + 2] in _HEX:
            out.append(uri[i:i + 3])
            i += 3
            continue
        if c in _URL_SAFE:
            out.append(c)
        else:
            try:
                data = c.encode('utf-8')
            except UnicodeEncodeError:
                data = '�'.encode('utf-8')
            out.append(''.join('%%%02X' % b for b in data))
        i += 1
    return ''.join(out)


def normalize_reference(label):
    """Normalize a link label (including its brackets) for matching."""
    inner = label[1:-1].strip(' \t\r\n')
    return RE_LABEL_WS.sub(' ', inner).casefold()


def is_unicode_whitespace(c):
    return c in '\t\n\f\r' or unicodedata.category(c) == 'Zs'


def is_unicode_punctuation(c):
    return unicodedata.category(c)[0] in 'PS'


def text(s):
    return Node('text', s)


class _Delimiter:
    __slots__ = ('cc', 'numdelims', 'origdelims', 'node', 'previous', 'next',
                 'can_open', 'can_close')


class _Bracket:
    __slots__ = ('node', 'previous', 'previous_delimiter', 'index', 'image',
                 'active', 'bracket_after')


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

    def _reset_memo(self):
        # Memoization that keeps pathological inputs linear: once a search
        # for a terminator starting at position p has failed, every later
        # search for the same terminator fails as well.
        self._no_terminator = {}
        self._bt_last = {}
        self._bt_scanned = False

    # -- low level -------------------------------------------------------
    def match(self, regex):
        m = regex.match(self.subject, self.pos)
        if m is None:
            return None
        self.pos = m.end()
        return m.group(0)

    def peek(self):
        if self.pos < len(self.subject):
            return self.subject[self.pos]
        return None

    def spnl(self):
        self.match(RE_SPNL)
        return True

    # -- entry points ----------------------------------------------------
    def parse(self, block, refmap):
        """Parse block.string_content into inline children of block."""
        self.refmap = refmap
        self.subject = block.string_content.strip(' \t\n')
        self.pos = 0
        self.delimiters = None
        self.brackets = None
        self._reset_memo()
        while self.parse_inline(block):
            pass
        block.string_content = ''
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
            block.append_child(text(c))
        return True

    # -- simple constructs ----------------------------------------------
    def parse_string(self, block):
        m = self.match(RE_MAIN)
        if m is None:
            return False
        block.append_child(text(m))
        return True

    def parse_newline(self, block):
        self.pos += 1
        last = block.last_child
        if last is not None and last.type == 'text' and last.literal.endswith(' '):
            hard = last.literal.endswith('  ')
            last.literal = last.literal.rstrip(' ')
            block.append_child(Node('linebreak' if hard else 'softbreak'))
        else:
            block.append_child(Node('softbreak'))
        self.match(RE_INITIAL_SPACE)
        return True

    def parse_backslash(self, block):
        subj = self.subject
        self.pos += 1
        c = self.peek()
        if c == '\n':
            self.pos += 1
            block.append_child(Node('linebreak'))
            self.match(RE_INITIAL_SPACE)
        elif c is not None and RE_ESCAPABLE.match(c):
            block.append_child(text(c))
            self.pos += 1
        else:
            block.append_child(text('\\'))
        return True

    def parse_backticks(self, block):
        ticks = self.match(RE_TICKS_HERE)
        if ticks is None:
            return False
        after_open = self.pos
        n_ticks = len(ticks)
        if self._bt_scanned and self._bt_last.get(n_ticks, -1) < after_open:
            block.append_child(text(ticks))
            return True
        while True:
            m = RE_TICKS.search(self.subject, self.pos)
            if m is None:
                self._bt_scanned = True
                break
            self.pos = m.end()
            run_len = m.end() - m.start()
            if m.start() > self._bt_last.get(run_len, -1):
                self._bt_last[run_len] = m.start()
            if run_len == n_ticks:
                contents = self.subject[after_open:m.start()].replace('\n', ' ')
                if (contents.strip(' ') and contents[0] == ' '
                        and contents[-1] == ' '):
                    contents = contents[1:-1]
                node = Node('code', contents)
                block.append_child(node)
                return True
        self.pos = after_open
        block.append_child(text(ticks))
        return True

    def parse_autolink(self, block):
        m = self.match(RE_EMAIL_AUTOLINK)
        if m is not None:
            dest = m[1:-1]
            node = Node('link')
            node.destination = normalize_uri('mailto:' + dest)
            node.title = ''
            node.append_child(text(dest))
            block.append_child(node)
            return True
        m = self.match(RE_AUTOLINK)
        if m is not None:
            dest = m[1:-1]
            node = Node('link')
            node.destination = normalize_uri(dest)
            node.title = ''
            node.append_child(text(dest))
            block.append_child(node)
            return True
        return False

    def _find_terminator(self, term, start):
        failed_from = self._no_terminator.get(term)
        if failed_from is not None and start >= failed_from:
            return -1
        idx = self.subject.find(term, start)
        if idx < 0:
            self._no_terminator[term] = start
        return idx

    def parse_html_tag(self, block):
        subj = self.subject
        pos = self.pos
        end = -1
        if subj.startswith('<?', pos):
            idx = self._find_terminator('?>', pos + 2)
            if idx >= 0:
                end = idx + 2
        elif subj.startswith('<!--', pos):
            if subj.startswith('<!-->', pos):
                end = pos + 5
            elif subj.startswith('<!--->', pos):
                end = pos + 6
            else:
                idx = self._find_terminator('-->', pos + 4)
                if idx >= 0:
                    end = idx + 3
        elif subj.startswith('<![CDATA[', pos):
            idx = self._find_terminator(']]>', pos + 9)
            if idx >= 0:
                end = idx + 3
        elif subj.startswith('<!', pos):
            if pos + 2 < len(subj) and subj[pos + 2] in _ASCII_LETTERS:
                idx = self._find_terminator('>', pos + 2)
                if idx >= 0:
                    end = idx + 1
        else:
            m = RE_OPEN_OR_CLOSE_TAG.match(subj, pos)
            if m is not None:
                end = m.end()
        if end < 0:
            return False
        self.pos = end
        block.append_child(Node('html_inline', subj[pos:end]))
        return True

    def parse_entity(self, block):
        m = self.match(RE_ENTITY_HERE)
        if m is None:
            return False
        block.append_child(text(decode_entity(m)))
        return True

    # -- emphasis ----------------------------------------------------------
    def scan_delims(self, cc):
        startpos = self.pos
        numdelims = 0
        subj = self.subject
        n = len(subj)
        while self.pos < n and subj[self.pos] == cc:
            numdelims += 1
            self.pos += 1
        if numdelims == 0:
            return None
        char_before = '\n' if startpos == 0 else subj[startpos - 1]
        char_after = '\n' if self.pos >= n else subj[self.pos]
        after_ws = is_unicode_whitespace(char_after)
        after_punct = is_unicode_punctuation(char_after)
        before_ws = is_unicode_whitespace(char_before)
        before_punct = is_unicode_punctuation(char_before)
        left_flanking = (not after_ws
                         and (not after_punct or before_ws or before_punct))
        right_flanking = (not before_ws
                          and (not before_punct or after_ws or after_punct))
        if cc == '_':
            can_open = left_flanking and (not right_flanking or before_punct)
            can_close = right_flanking and (not left_flanking or after_punct)
        else:
            can_open = left_flanking
            can_close = right_flanking
        self.pos = startpos
        return numdelims, can_open, can_close

    def handle_delim(self, cc, block):
        res = self.scan_delims(cc)
        if res is None:
            return False
        numdelims, can_open, can_close = res
        startpos = self.pos
        self.pos += numdelims
        node = text(self.subject[startpos:self.pos])
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
        openers_bottom = [stack_bottom] * 14
        closer = self.delimiters
        while closer is not None and closer.previous is not stack_bottom:
            closer = closer.previous
        while closer is not None:
            if not closer.can_close:
                closer = closer.next
                continue
            closercc = closer.cc
            if closercc == '_':
                idx = 2 + (3 if closer.can_open else 0) + closer.origdelims % 3
            else:
                idx = 8 + (3 if closer.can_open else 0) + closer.origdelims % 3
            opener = closer.previous
            opener_found = False
            while (opener is not None and opener is not stack_bottom
                   and opener is not openers_bottom[idx]):
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
                use_delims = 2 if (closer.numdelims >= 2 and opener.numdelims >= 2) else 1
                opener_inl = opener.node
                closer_inl = closer.node
                opener.numdelims -= use_delims
                closer.numdelims -= use_delims
                opener_inl.literal = opener_inl.literal[:len(opener_inl.literal) - use_delims]
                closer_inl.literal = closer_inl.literal[:len(closer_inl.literal) - use_delims]
                emph = Node('emph' if use_delims == 1 else 'strong')
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

    # -- links and images ------------------------------------------------
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
        node = text('[')
        block.append_child(node)
        self.add_bracket(node, startpos, False)
        return True

    def parse_bang(self, block):
        startpos = self.pos
        self.pos += 1
        if self.peek() == '[':
            self.pos += 1
            node = text('![')
            block.append_child(node)
            self.add_bracket(node, startpos + 1, True)
        else:
            block.append_child(text('!'))
        return True

    def parse_link_label(self):
        m = self.match(RE_LINK_LABEL)
        if m is None or len(m) > 1001:
            return 0
        return len(m)

    def parse_link_destination(self, allow_empty=True):
        res = self.match(RE_LINK_DEST_BRACES)
        if res is not None:
            return normalize_uri(unescape_string(res[1:-1]))
        if self.peek() == '<':
            return None
        subj = self.subject
        n = len(subj)
        savepos = self.pos
        openparens = 0
        c = None
        while self.pos < n:
            c = subj[self.pos]
            if c == '\\' and self.pos + 1 < n and RE_ESCAPABLE.match(subj[self.pos + 1]):
                self.pos += 2
            elif c == '(':
                self.pos += 1
                openparens += 1
            elif c == ')':
                if openparens < 1:
                    break
                self.pos += 1
                openparens -= 1
            elif c <= ' ' or c == '\x7f':
                break
            else:
                self.pos += 1
        else:
            c = None
        if self.pos == savepos and (c != ')' or not allow_empty):
            self.pos = savepos
            return None
        if openparens != 0:
            self.pos = savepos
            return None
        res = subj[savepos:self.pos]
        return normalize_uri(unescape_string(res))

    def parse_link_title(self):
        m = self.match(RE_LINK_TITLE)
        if m is None:
            return None
        return unescape_string(m[1:-1])

    def parse_close_bracket(self, block):
        self.pos += 1
        startpos = self.pos
        opener = self.brackets
        if opener is None:
            block.append_child(text(']'))
            return True
        if not opener.active:
            block.append_child(text(']'))
            self.remove_bracket()
            return True
        is_image = opener.image
        savepos = self.pos
        matched = False
        dest = None
        title = None

        # Inline link?
        if self.peek() == '(':
            self.pos += 1
            self.spnl()
            dest = self.parse_link_destination()
            ok = False
            if dest is not None:
                self.spnl()
                if self.subject[self.pos - 1] in ' \t\n':
                    title = self.parse_link_title()
                self.spnl()
                if self.peek() == ')':
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
            n = self.parse_link_label()
            reflabel = None
            if n > 2:
                reflabel = self.subject[beforelabel:beforelabel + n]
            elif not opener.bracket_after:
                reflabel = self.subject[opener.index:startpos]
            if n == 0:
                self.pos = savepos
            if reflabel is not None:
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
                op = self.brackets
                while op is not None:
                    if not op.image:
                        op.active = False
                    op = op.previous
            return True

        self.remove_bracket()
        self.pos = startpos
        block.append_child(text(']'))
        return True

    # -- link reference definitions ---------------------------------------
    def parse_reference(self, s, refmap, start=0):
        """Try to parse a link reference definition at s[start:].

        Returns the number of characters consumed (0 if none)."""
        self.subject = s
        self.pos = start
        startpos = start
        n = self.parse_link_label()
        if n == 0:
            return 0
        rawlabel = s[start:start + n]
        if self.peek() == ':':
            self.pos += 1
        else:
            self.pos = startpos
            return 0
        self.spnl()
        dest = self.parse_link_destination(allow_empty=False)
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
        if self.match(RE_SPACE_AT_END_OF_LINE) is None:
            if title is None:
                at_line_end = False
            else:
                title = None
                self.pos = beforetitle
                at_line_end = self.match(RE_SPACE_AT_END_OF_LINE) is not None
        if not at_line_end:
            self.pos = startpos
            return 0
        normlabel = normalize_reference(rawlabel)
        if normlabel == '':
            self.pos = startpos
            return 0
        if normlabel not in refmap:
            refmap[normlabel] = (dest, title)
        return self.pos - startpos
