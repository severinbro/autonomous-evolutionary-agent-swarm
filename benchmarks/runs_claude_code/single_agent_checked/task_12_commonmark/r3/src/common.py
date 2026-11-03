"""Shared helpers: escaping, entity decoding, URL and label normalization."""
import re
from html.entities import html5 as _HTML5

ESCAPABLE = r"""[!"#$%&'()*+,./:;<=>?@\[\\\]^_`{|}~-]"""
ENTITY = r"&(?:#[xX][0-9a-fA-F]{1,6}|#[0-9]{1,7}|[A-Za-z][A-Za-z0-9]{1,31});"

WS = r"[ \t\n\r\f\v]"
TAGNAME = r"[A-Za-z][A-Za-z0-9-]*"
ATTRIBUTENAME = r"[a-zA-Z_:][a-zA-Z0-9:._-]*"
UNQUOTEDVALUE = r"[^\"'=<>`\x00-\x20]+"
SINGLEQUOTEDVALUE = r"'[^']*'"
DOUBLEQUOTEDVALUE = r'"[^"]*"'
ATTRIBUTEVALUE = "(?:" + UNQUOTEDVALUE + "|" + SINGLEQUOTEDVALUE + "|" + DOUBLEQUOTEDVALUE + ")"
ATTRIBUTEVALUESPEC = "(?:" + WS + "*=" + WS + "*" + ATTRIBUTEVALUE + ")"
ATTRIBUTE = "(?:" + WS + "+" + ATTRIBUTENAME + ATTRIBUTEVALUESPEC + "?)"
OPENTAG = "<" + TAGNAME + ATTRIBUTE + "*" + WS + "*/?>"
CLOSETAG = "</" + TAGNAME + WS + "*>"
HTMLCOMMENT = r"<!-->|<!--->|<!--[\s\S]*?-->"
PROCESSINGINSTRUCTION = r"<\?[\s\S]*?\?>"
DECLARATION = r"<![A-Za-z][^>]*>"
CDATA = r"<!\[CDATA\[[\s\S]*?\]\]>"
HTMLTAG = ("(?:" + OPENTAG + "|" + CLOSETAG + "|" + HTMLCOMMENT + "|" +
           PROCESSINGINSTRUCTION + "|" + DECLARATION + "|" + CDATA + ")")

_RE_UNESCAPE = re.compile(r"\\(" + ESCAPABLE + ")|(" + ENTITY + ")")
_RE_WS_RUN = re.compile(r"[ \t\r\n]+")


def decode_entity(ent):
    """Decode an entity or numeric character reference (including & and ;).

    Returns None when a named entity is unknown."""
    body = ent[1:-1]
    if body.startswith('#'):
        if body[1:2] in ('x', 'X'):
            cp = int(body[2:], 16)
        else:
            cp = int(body[1:], 10)
        if cp == 0 or cp > 0x10FFFF or 0xD800 <= cp <= 0xDFFF:
            return '�'
        return chr(cp)
    return _HTML5.get(body + ';')


def _unescape_repl(m):
    if m.group(1) is not None:
        return m.group(1)
    ent = m.group(2)
    dec = decode_entity(ent)
    return ent if dec is None else dec


def unescape_string(s):
    """Process backslash escapes and entity references."""
    if '\\' not in s and '&' not in s:
        return s
    return _RE_UNESCAPE.sub(_unescape_repl, s)


_HREF_SAFE = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    "-_.+!*'(),%#@?=;:/&$~")


def normalize_uri(uri):
    """Percent-encode characters that are not safe in a URL."""
    out = []
    for ch in uri:
        if ch in _HREF_SAFE:
            out.append(ch)
        else:
            for b in ch.encode('utf-8', 'surrogatepass'):
                out.append('%%%02X' % b)
    return ''.join(out)


def escape_html(s):
    if not s:
        return ''
    return (s.replace('&', '&amp;').replace('<', '&lt;')
             .replace('>', '&gt;').replace('"', '&quot;'))


def normalize_reference(label):
    """Normalize a link label (including its surrounding brackets)."""
    inner = label[1:-1]
    inner = _RE_WS_RUN.sub(' ', inner).strip(' ')
    return inner.casefold()
