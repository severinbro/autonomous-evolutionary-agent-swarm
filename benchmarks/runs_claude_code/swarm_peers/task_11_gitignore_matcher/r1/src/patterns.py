"""Parsing of ``.gitignore`` lines into patterns and glob matching.

Implements the pattern format described in gitignore(5):

* blank lines are ignored; lines starting with ``#`` are comments
  (``\\#`` escapes a literal leading hash);
* trailing spaces are dropped unless escaped with a backslash;
* a leading ``!`` negates the pattern (``\\!`` escapes a literal ``!``);
* a trailing ``/`` makes the pattern match directories only;
* a pattern containing a ``/`` at the start or in the middle is matched
  against the full path relative to the ``.gitignore`` location, otherwise
  it is matched against the last path component (the basename) at any depth;
* ``*``, ``?``, ``[...]`` (with ``!``/``^`` negation, ranges and POSIX
  ``[:class:]`` names), backslash escapes and the ``**`` forms ``**/x``,
  ``x/**`` and ``a/**/b`` are supported, with ``*``/``?``/``[]`` never
  matching ``/`` in path patterns.

Matching works on UTF-8 bytes, like Git, so ``?`` matches a single byte.
"""

from __future__ import annotations

_GLOB_SPECIAL = frozenset(b"*?[\\")

_MATCH = 0
_NOMATCH = 1
_ABORT_ALL = -1
_ABORT_TO_STARSTAR = -2

_SLASH = 0x2F
_BACKSLASH = 0x5C


def _to_bytes(value) -> bytes:
    if isinstance(value, bytes):
        return value
    return value.encode("utf-8", "surrogateescape")


def _is_ascii(c: int) -> bool:
    return c < 0x80


def _cls_alnum(c):
    return _cls_alpha(c) or _cls_digit(c)


def _cls_alpha(c):
    return 0x41 <= c <= 0x5A or 0x61 <= c <= 0x7A


def _cls_blank(c):
    return c in (0x20, 0x09)


def _cls_cntrl(c):
    return c < 0x20 or c == 0x7F


def _cls_digit(c):
    return 0x30 <= c <= 0x39


def _cls_graph(c):
    return 0x21 <= c <= 0x7E


def _cls_lower(c):
    return 0x61 <= c <= 0x7A


def _cls_print(c):
    return 0x20 <= c <= 0x7E


def _cls_punct(c):
    return _cls_graph(c) and not _cls_alnum(c)


def _cls_space(c):
    return c in (0x20, 0x09, 0x0A, 0x0B, 0x0C, 0x0D)


def _cls_upper(c):
    return 0x41 <= c <= 0x5A


def _cls_xdigit(c):
    return _cls_digit(c) or 0x41 <= c <= 0x46 or 0x61 <= c <= 0x66


_CLASSES = {
    b"alnum": _cls_alnum,
    b"alpha": _cls_alpha,
    b"blank": _cls_blank,
    b"cntrl": _cls_cntrl,
    b"digit": _cls_digit,
    b"graph": _cls_graph,
    b"lower": _cls_lower,
    b"print": _cls_print,
    b"punct": _cls_punct,
    b"space": _cls_space,
    b"upper": _cls_upper,
    b"xdigit": _cls_xdigit,
}


def _dowild(pat: bytes, p: int, text: bytes, t: int, pathname: bool) -> int:
    """Port of Git's wildmatch algorithm over byte strings.

    ``p``/``t`` are indices into ``pat``/``text``; ``start`` is the index at
    which this (possibly recursive) invocation's pattern begins, which is
    what decides whether a ``**`` sits at the start of the pattern.
    """
    start = p
    plen = len(pat)
    tlen = len(text)
    while p < plen:
        p_ch = pat[p]
        t_ch = text[t] if t < tlen else 0
        if t >= tlen and p_ch != 0x2A:  # '*'
            return _ABORT_ALL
        if p_ch == _BACKSLASH:
            # Literal match with the following character; a trailing
            # backslash never matches anything.
            p += 1
            p_ch = pat[p] if p < plen else 0
            if t_ch != p_ch:
                return _NOMATCH
            p += 1
            t += 1
            continue
        if p_ch == 0x3F:  # '?'
            if pathname and t_ch == _SLASH:
                return _NOMATCH
            p += 1
            t += 1
            continue
        if p_ch == 0x2A:  # '*'
            p += 1
            if p < plen and pat[p] == 0x2A:
                prev_p = p - 2
                while p < plen and pat[p] == 0x2A:
                    p += 1
                nxt = pat[p] if p < plen else 0
                if not pathname:
                    # Without pathname semantics '*' == '**'.
                    match_slash = True
                elif (prev_p < start or pat[prev_p] == _SLASH) and (
                    nxt == 0
                    or nxt == _SLASH
                    or (nxt == _BACKSLASH and p + 1 < plen and pat[p + 1] == _SLASH)
                ):
                    if nxt == _SLASH and _dowild(pat, p + 1, text, t, pathname) == _MATCH:
                        return _MATCH
                    match_slash = True
                else:
                    match_slash = not pathname
            else:
                match_slash = not pathname
            if p >= plen:
                # Trailing "**" matches everything; trailing "*" only if no
                # more slashes follow.
                if not match_slash and text.find(b"/", t) != -1:
                    return _NOMATCH
                return _MATCH
            if not match_slash and pat[p] == _SLASH:
                # A single "*" followed by "/" matches the rest of the
                # current path component.
                slash = text.find(b"/", t)
                if slash == -1:
                    return _NOMATCH
                t = slash
                # The slash itself is consumed by the main loop below.
                p += 1
                t += 1
                continue
            while True:
                if t >= tlen:
                    break
                if pat[p] not in _GLOB_SPECIAL:
                    lit = pat[p]
                    while t < tlen and (match_slash or text[t] != _SLASH):
                        if text[t] == lit:
                            break
                        t += 1
                    if t >= tlen or text[t] != lit:
                        return _NOMATCH
                matched = _dowild(pat, p, text, t, pathname)
                if matched != _NOMATCH:
                    if not match_slash or matched != _ABORT_TO_STARSTAR:
                        return matched
                elif not match_slash and text[t] == _SLASH:
                    return _ABORT_TO_STARSTAR
                t += 1
            return _ABORT_ALL
        if p_ch == 0x5B:  # '['
            p += 1
            p_ch = pat[p] if p < plen else 0
            if p_ch == 0x5E:  # '^' behaves like '!'
                p_ch = 0x21
            negated = p_ch == 0x21
            if negated:
                p += 1
                p_ch = pat[p] if p < plen else 0
            prev_ch = 0
            matched = False
            while True:
                if p_ch == 0:
                    return _ABORT_ALL
                if p_ch == _BACKSLASH:
                    p += 1
                    p_ch = pat[p] if p < plen else 0
                    if p_ch == 0:
                        return _ABORT_ALL
                    if t_ch == p_ch:
                        matched = True
                elif (
                    p_ch == 0x2D  # '-'
                    and prev_ch
                    and p + 1 < plen
                    and pat[p + 1] != 0x5D
                ):
                    p += 1
                    p_ch = pat[p]
                    if p_ch == _BACKSLASH:
                        p += 1
                        p_ch = pat[p] if p < plen else 0
                        if p_ch == 0:
                            return _ABORT_ALL
                    if prev_ch <= t_ch <= p_ch:
                        matched = True
                    p_ch = 0  # so that prev_ch becomes 0
                elif p_ch == 0x5B and p + 1 < plen and pat[p + 1] == 0x3A:  # "[:"
                    s = p + 2
                    p = s
                    while p < plen and pat[p] != 0x5D:
                        p += 1
                    if p >= plen:
                        return _ABORT_ALL
                    i = p - s - 1
                    if i < 0 or pat[p - 1] != 0x3A:
                        # No ":]", treat "[" as a normal set member.
                        p = s - 2
                        p_ch = 0x5B
                        if t_ch == p_ch:
                            matched = True
                    else:
                        name = pat[s:s + i]
                        func = _CLASSES.get(name)
                        if func is None:
                            return _ABORT_ALL
                        if _is_ascii(t_ch) and func(t_ch):
                            matched = True
                        p_ch = 0
                elif t_ch == p_ch:
                    matched = True
                prev_ch = p_ch
                p += 1
                p_ch = pat[p] if p < plen else 0
                if p_ch == 0x5D:  # ']'
                    break
            if matched == negated or (pathname and t_ch == _SLASH):
                return _NOMATCH
            p += 1
            t += 1
            continue
        # Ordinary character.
        if t_ch != p_ch:
            return _NOMATCH
        p += 1
        t += 1
    return _NOMATCH if t < tlen else _MATCH


def wildmatch(pattern, text, pathname: bool = True) -> bool:
    """Return True if ``text`` matches glob ``pattern``.

    With ``pathname`` set, ``*``, ``?`` and bracket expressions never match
    ``/`` and ``**`` gets its special directory-spanning meaning (Git's
    ``WM_PATHNAME``). Without it ``*`` matches any sequence including ``/``.
    Accepts ``str`` or ``bytes``.
    """
    pat = _to_bytes(pattern)
    txt = _to_bytes(text)
    return _dowild(pat, 0, txt, 0, pathname) == _MATCH


def _simple_length(pat: bytes) -> int:
    """Length of the leading run of characters without glob specials."""
    for i, c in enumerate(pat):
        if c in _GLOB_SPECIAL:
            return i
    return len(pat)


def trim_trailing_spaces(line: str) -> str:
    """Drop unescaped trailing spaces (only ``' '``, not tabs)."""
    last_space = None
    i = 0
    n = len(line)
    while i < n:
        ch = line[i]
        if ch == " ":
            if last_space is None:
                last_space = i
        elif ch == "\\":
            i += 1
            if i >= n:
                return line
            last_space = None
        else:
            last_space = None
        i += 1
    if last_space is not None:
        return line[:last_space]
    return line


class Pattern:
    """A single parsed ``.gitignore`` pattern."""

    __slots__ = ("source", "pattern", "negated", "dir_only", "anchored", "_bytes", "_prefix")

    def __init__(self, pattern: str, negated: bool = False, dir_only: bool = False,
                 anchored: bool = False, source: str | None = None):
        self.pattern = pattern
        self.negated = negated
        self.dir_only = dir_only
        self.anchored = anchored
        self.source = pattern if source is None else source
        pat = _to_bytes(pattern)
        prefix = _simple_length(pat)
        if anchored and pat[:1] == b"/":
            pat = pat[1:]
            prefix -= 1
        self._bytes = pat
        self._prefix = prefix

    def __repr__(self) -> str:
        return (f"Pattern({self.pattern!r}, negated={self.negated}, "
                f"dir_only={self.dir_only}, anchored={self.anchored})")

    def match(self, path: str, is_dir: bool = False) -> bool:
        """Whether this pattern matches ``path`` (ignoring negation).

        ``path`` is relative to the repository root, without leading or
        trailing slash; ``is_dir`` tells whether it names a directory.
        """
        if self.dir_only and not is_dir:
            return False
        name = _to_bytes(path)
        if not name:
            return False
        if not self.anchored:
            base = name[name.rfind(b"/") + 1:]
            return _dowild(self._bytes, 0, base, 0, False) == _MATCH
        pat = self._bytes
        prefix = self._prefix
        if prefix > 0:
            # Compare the literal prefix, then glob the rest (as Git does,
            # which makes a "**" right after the prefix count as leading).
            if prefix > len(name) or name[:prefix] != pat[:prefix]:
                return False
            pat = pat[prefix:]
            name = name[prefix:]
            if not pat and not name:
                return True
        return _dowild(pat, 0, name, 0, True) == _MATCH


def parse_line(line: str) -> Pattern | None:
    """Parse one ``.gitignore`` line (without its newline).

    Returns None for blank lines and comments.
    """
    if line.endswith("\r"):
        line = line[:-1]
    if not line or line.startswith("#"):
        return None
    source = line
    line = trim_trailing_spaces(line)
    if not line:
        return None
    negated = False
    if line.startswith("!"):
        negated = True
        line = line[1:]
    dir_only = False
    if line.endswith("/"):
        dir_only = True
        line = line[:-1]
    anchored = "/" in line
    if not line:
        return None
    return Pattern(line, negated=negated, dir_only=dir_only, anchored=anchored,
                   source=source)


def parse(text: str) -> list[Pattern]:
    """Parse the full text of a ``.gitignore`` file into patterns in order."""
    if text.startswith("﻿"):
        text = text[1:]
    patterns = []
    for line in text.split("\n"):
        pat = parse_line(line)
        if pat is not None:
            patterns.append(pat)
    return patterns
