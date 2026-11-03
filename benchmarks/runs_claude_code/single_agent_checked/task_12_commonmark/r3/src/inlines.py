"""Inline parsing for CommonMark (code spans, emphasis, links, etc.)."""
import re
import unicodedata

from .node import Node
from .common import (ESCAPABLE, ENTITY, HTMLTAG, decode_entity,
                     unescape_string, normalize_uri, normalize_reference)

RE_ESCAPABLE = re.compile(ESCAPABLE)
RE_ENTITY_HERE = re.compile(ENTITY)
RE_TICKS = re.compile(r'`+')
RE_TICKS_HERE = re.compile(r'`+')
RE_EMAIL_AUTOLINK = re.compile(
    r"<([a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}"
    r"[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*)>")
RE_AUTOLINK = re.compile(r"<[A-Za-z][A-Za-z0-9.+-]{1,31}:[^<>\x00-\x20]*>")
RE_HTML_TAG = re.compile(HTMLTAG, re.IGNORECASE)
RE_SPNL = re.compile(r'[ \t]*(?:\n[ \t]*)?')
RE_INITIAL_SPACE = re.compile(r'[ \t]*')
RE_SPACE_AT_END_OF_LINE = re.compile(r'[ \t]*(?:\n|\Z)')
RE_LINK_LABEL = re.compile(r'\[(?:[^\\\[\]]|\\.){0,1000}\]', re.S)
RE_LINK_DESTINATION_BRACES = re.compile(r'<(?:[^<>\n\\\x00]|\\.)*>', re.S)
RE_LINK_TITLE = re.compile(
    r'"(?:\\[\s\S]|[^\\"\x00])*"'
    r"|'(?:\\[\s\S]|[^\\'\x00])*'"
    r'|\((?:\\[\s\S]|[^\\()\x00])*\)')
RE_MAIN = re.compile(r'[^\n`\[\]\\!<&*_]+')
RE_CODE_NONSPACE = re.compile(r'[^ ]')

WHITESPACE_CHARS = ' \t\n\x0b\x0c\x0d'


def is_unicode_whitespace(ch):
    if ch in ('\t', '\n', '\x0c', '\r'):
        return True
    return unicodedata.category(ch) == 'Zs'


def is_punctuation(ch):
    return unicodedata.category(ch)[0] in ('P', 'S')


def text(s):
    return Node('text', s)


class Delimiter:
    __slots__ = ('cc', 'numdelims', 'origdelims', 'node', 'previous', 'next',
                 'can_open', 'can_close')


class Bracket:
    __slots__ = ('node', 'previous', 'previous_delimiter', 'index', 'image',
                 'active', 'bracket_after')


class InlineParser:
    def __init__(self):
        self.subject = ''
        self.pos = 0
        self.delimiters = None
        self.brackets = None
        self.refmap = {}

    # -- helpers ---------------------------------------------------------
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
        self.match(RE_SPNL)
        return True

    # -- entry point -----------------------------------------------------
    def parse(self, block, refmap):
        self.refmap = refmap
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
            block.append_child(text(c))
        return True

    # -- individual constructs --------------------------------------------
    def parse_newline(self, block):
        self.pos += 1
        lastc = block.last_child
        if (lastc is not None and lastc.type == 'text' and lastc.literal
                and lastc.literal[-1] in (' ', '\t')):
            hardbreak = lastc.literal.endswith('  ')
            lastc.literal = lastc.literal.rstrip(' \t')
            block.append_child(Node('linebreak' if hardbreak else 'softbreak'))
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
        while True:
            m = RE_TICKS.search(self.subject, self.pos)
            if m is None:
                break
            self.pos = m.end()
            if m.group(0) == ticks:
                contents = self.subject[after_open:m.start()].replace('\n', ' ')
                if (len(contents) > 0 and RE_CODE_NONSPACE.search(contents)
                        and contents[0] == ' ' and contents[-1] == ' '):
                    contents = contents[1:-1]
                block.append_child(Node('code', contents))
                return True
        self.pos = after_open
        block.append_child(text(ticks))
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
        char_after = self.peek()
        if char_after is None:
            char_after = '\n'
        after_ws = is_unicode_whitespace(char_after)
        after_punct = is_punctuation(char_after)
        before_ws = is_unicode_whitespace(char_before)
        before_punct = is_punctuation(char_before)
        left_flanking = (not after_ws and
                         (not after_punct or before_ws or before_punct))
        right_flanking = (not before_ws and
                          (not before_punct or after_ws or after_punct))
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
            d = Delimiter()
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
        openers_bottom = {}
        closer = self.delimiters
        while closer is not None and closer.previous is not stack_bottom:
            closer = closer.previous
        while closer is not None:
            if not closer.can_close:
                closer = closer.next
                continue
            closercc = closer.cc
            opener = closer.previous
            opener_found = False
            idx = ((0 if closercc == '_' else 6) +
                   (3 if closer.can_open else 0) + closer.origdelims % 3)
            bottom = openers_bottom.get(idx, stack_bottom)
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
                openers_bottom[idx] = old_closer.previous
                if not old_closer.can_open:
                    self.remove_delimiter(old_closer)
        while self.delimiters is not None and self.delimiters is not stack_bottom:
            self.remove_delimiter(self.delimiters)

    def add_bracket(self, node, index, image):
        if self.brackets is not None:
            self.brackets.bracket_after = True
        b = Bracket()
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

    def parse_link_destination(self):
        res = self.match(RE_LINK_DESTINATION_BRACES)
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
            elif c in WHITESPACE_CHARS or ord(c) < 0x20 or ord(c) == 0x7f:
                break
            else:
                self.pos += 1
        else:
            c = None
        if self.pos == savepos and c != ')':
            return None
        if openparens != 0:
            return None
        res = subj[savepos:self.pos]
        return normalize_uri(unescape_string(res))

    def parse_link_title(self):
        title = self.match(RE_LINK_TITLE)
        if title is None:
            return None
        return unescape_string(title[1:-1])

    def parse_link_label(self):
        m = RE_LINK_LABEL.match(self.subject, self.pos)
        if m is None or len(m.group(0)) > 1001:
            return 0
        self.pos = m.end()
        return len(m.group(0))

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
        if self.peek() == '(':
            self.pos += 1
            self.spnl()
            dest = self.parse_link_destination()
            ok = False
            if dest is not None:
                self.spnl()
                if self.subject[self.pos - 1] in WHITESPACE_CHARS:
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
            reflabel = None
            beforelabel = self.pos
            n = self.parse_link_label()
            if n > 2:
                reflabel = self.subject[beforelabel:beforelabel + n]
            elif not opener.bracket_after:
                reflabel = self.subject[opener.index:startpos]
                if len(reflabel) > 1001:
                    reflabel = None
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
                tmp.unlink()
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

    def parse_html_tag(self, block):
        m = self.match(RE_HTML_TAG)
        if m is None:
            return False
        block.append_child(Node('html_inline', m))
        return True

    def parse_entity(self, block):
        m = self.match(RE_ENTITY_HERE)
        if m is None:
            return False
        dec = decode_entity(m)
        block.append_child(text(m if dec is None else dec))
        return True

    def parse_string(self, block):
        m = self.match(RE_MAIN)
        if m is None:
            return False
        block.append_child(text(m))
        return True

    # -- link reference definitions ---------------------------------------
    def parse_reference(self, s, refmap):
        """Try to parse a link reference definition at the start of s.

        Returns the number of characters consumed (0 if none)."""
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
        beforedest = self.pos
        dest = self.parse_link_destination()
        if dest is None or (self.pos == beforedest):
            self.pos = startpos
            return 0
        beforetitle = self.pos
        self.spnl()
        title = None
        if self.pos != beforetitle:
            title = self.parse_link_title()
        if title is None:
            title = ''
            self.pos = beforetitle
            at_line_end = self.match(RE_SPACE_AT_END_OF_LINE) is not None
        else:
            at_line_end = self.match(RE_SPACE_AT_END_OF_LINE) is not None
            if not at_line_end:
                title = ''
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
