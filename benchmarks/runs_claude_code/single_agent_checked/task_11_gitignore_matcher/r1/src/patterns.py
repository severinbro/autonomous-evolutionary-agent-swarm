"""Parsing of .gitignore lines into patterns, plus the glob matcher they use.

The semantics follow gitignore(5):

* blank lines match nothing; lines starting with ``#`` are comments
  (``\\#`` escapes a literal leading hash);
* trailing spaces are ignored unless escaped with a backslash;
* a leading ``!`` negates the pattern (``\\!`` escapes a literal ``!``);
* a trailing ``/`` makes the pattern match directories only;
* a pattern containing a ``/`` (other than a trailing one) is anchored to
  the directory of the .gitignore file and matched against the full path;
  otherwise it is matched against the basename at any depth;
* ``*``, ``?`` and ``[...]`` never match ``/``; ``**`` between slashes, at
  the start (``**/``) or end (``/**``) matches across directories; other
  runs of asterisks behave like a single ``*``.
"""

from __future__ import annotations

from dataclasses import dataclass

# Results of the glob matcher (mirroring the classic wildmatch algorithm).
MATCH = 0
NOMATCH = 1
ABORT_ALL = -1
ABORT_TO_STARSTAR = -2

_GLOB_SPECIAL = "*?[\\"


def _is_glob_special(ch: str) -> bool:
    return ch != "" and ch in _GLOB_SPECIAL


def _char_class(name: str, ch: str):
    """Return True/False for a POSIX class test, or None if class unknown."""
    if ch == "":
        return False
    o = ord(ch)
    is_ascii = o < 128
    if name == "alnum":
        return is_ascii and ch.isalnum()
    if name == "alpha":
        return is_ascii and ch.isalpha()
    if name == "blank":
        return ch in " \t"
    if name == "cntrl":
        return o < 32 or o == 127
    if name == "digit":
        return "0" <= ch <= "9"
    if name == "graph":
        return 33 <= o <= 126
    if name == "lower":
        return "a" <= ch <= "z"
    if name == "print":
        return 32 <= o <= 126
    if name == "punct":
        return 33 <= o <= 126 and not ch.isalnum()
    if name == "space":
        return ch in " \t\n\r\f\v"
    if name == "upper":
        return "A" <= ch <= "Z"
    if name == "xdigit":
        return ch in "0123456789abcdefABCDEF"
    return None


def _dowild(pat: str, p: int, text: str, t: int, pathname: bool) -> int:
    """Match pat[p:] against text[t:]; returns MATCH/NOMATCH/ABORT_*."""
    start = p
    plen = len(pat)
    tlen = len(text)

    def pc(i: int) -> str:
        return pat[i] if i < plen else ""

    while p < plen:
        p_ch = pat[p]
        t_ch = text[t] if t < tlen else ""
        if t_ch == "" and p_ch != "*":
            return ABORT_ALL

        if p_ch == "\\":
            # Literal match with the following character; a trailing
            # backslash can never match anything.
            p += 1
            p_ch = pc(p)
            if p_ch == "" or t_ch != p_ch:
                return NOMATCH
        elif p_ch == "?":
            if pathname and t_ch == "/":
                return NOMATCH
        elif p_ch == "*":
            p += 1
            if pc(p) == "*":
                prev_p = p - 2
                p += 1
                while pc(p) == "*":
                    p += 1
                if (prev_p < start or pat[prev_p] == "/") and (
                    pc(p) == ""
                    or pc(p) == "/"
                    or (pc(p) == "\\" and pc(p + 1) == "/")
                ):
                    # "**/" may match zero directories.
                    if pc(p) == "/" and _dowild(pat, p + 1, text, t, pathname) == MATCH:
                        return MATCH
                    match_slash = True
                else:
                    match_slash = not pathname
            else:
                match_slash = not pathname

            if pc(p) == "":
                # Trailing "**" matches everything; trailing "*" only if
                # no slash remains.
                if not match_slash and "/" in text[t:]:
                    return NOMATCH
                return MATCH
            if not match_slash and pc(p) == "/":
                # A single star followed by a slash matches up to the
                # next directory separator.
                slash = text.find("/", t)
                if slash < 0:
                    return NOMATCH
                t = slash
                # The slash itself is consumed by the main loop below.
                t += 1
                p += 1
                continue

            while True:
                if t >= tlen:
                    break
                if not _is_glob_special(pc(p)):
                    lit = pc(p)
                    while t < tlen and (match_slash or text[t] != "/"):
                        if text[t] == lit:
                            break
                        t += 1
                    cur = text[t] if t < tlen else ""
                    if cur != lit:
                        return NOMATCH
                matched = _dowild(pat, p, text, t, pathname)
                if matched != NOMATCH:
                    if not match_slash or matched != ABORT_TO_STARSTAR:
                        return matched
                elif not match_slash and text[t] == "/":
                    return ABORT_TO_STARSTAR
                t += 1
            return ABORT_ALL
        elif p_ch == "[":
            p += 1
            p_ch = pc(p)
            if p_ch == "^":
                p_ch = "!"
            negated = p_ch == "!"
            if negated:
                p += 1
                p_ch = pc(p)
            prev_ch = ""
            matched_set = False
            while True:
                if p_ch == "":
                    return ABORT_ALL
                if p_ch == "\\":
                    p += 1
                    p_ch = pc(p)
                    if p_ch == "":
                        return ABORT_ALL
                    if t_ch == p_ch:
                        matched_set = True
                elif p_ch == "-" and prev_ch != "" and pc(p + 1) not in ("", "]"):
                    p += 1
                    p_ch = pc(p)
                    if p_ch == "\\":
                        p += 1
                        p_ch = pc(p)
                        if p_ch == "":
                            return ABORT_ALL
                    if prev_ch <= t_ch <= p_ch:
                        matched_set = True
                    p_ch = ""  # resets prev_ch
                elif p_ch == "[" and pc(p + 1) == ":":
                    s = p + 2
                    q = s
                    while pc(q) not in ("", "]"):
                        q += 1
                    if pc(q) == "":
                        return ABORT_ALL
                    i = q - s - 1
                    if i < 0 or pat[q - 1] != ":":
                        # Not a "[:class:]"; treat '[' as an ordinary member.
                        p_ch = "["
                        if t_ch == p_ch:
                            matched_set = True
                    else:
                        res = _char_class(pat[s:s + i], t_ch)
                        if res is None:
                            return ABORT_ALL
                        if res:
                            matched_set = True
                        p = q
                        p_ch = ""
                elif t_ch == p_ch:
                    matched_set = True
                prev_ch = p_ch
                p += 1
                p_ch = pc(p)
                if p_ch == "]":
                    break
            if matched_set == negated or (pathname and t_ch == "/"):
                return NOMATCH
        else:
            if t_ch != p_ch:
                return NOMATCH
        p += 1
        t += 1

    return NOMATCH if t < tlen else MATCH


def wildmatch(pattern: str, text: str, pathname: bool = True) -> bool:
    """Glob-match ``text`` against ``pattern``.

    With ``pathname`` set, ``*``, ``?`` and bracket expressions do not match
    ``/`` and ``**`` gets its directory-spanning meaning.
    """
    return _dowild(pattern, 0, text, 0, pathname) == MATCH


def simple_length(pattern: str) -> int:
    """Length of the leading part of ``pattern`` free of glob characters."""
    for i, ch in enumerate(pattern):
        if ch in _GLOB_SPECIAL:
            return i
    return len(pattern)


def _trim_trailing_spaces(line: str) -> str:
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


@dataclass(frozen=True)
class Pattern:
    """One parsed .gitignore pattern."""

    source: str        # the original line (after trimming)
    pattern: str       # glob text, without "!" and trailing "/"
    negative: bool     # line started with "!"
    must_be_dir: bool  # line ended with "/"
    no_dir: bool       # no "/" in the pattern: match the basename only
    prefix_len: int    # length of the literal (wildcard-free) prefix

    def matches(self, path: str, is_dir: bool) -> bool:
        """Whether this pattern matches ``path`` (relative to the root)."""
        if self.must_be_dir and not is_dir:
            return False
        if self.no_dir:
            basename = path.rsplit("/", 1)[-1]
            if self.prefix_len == len(self.pattern):
                return self.pattern == basename
            return wildmatch(self.pattern, basename, pathname=False)
        pat = self.pattern
        prefix = self.prefix_len
        if pat.startswith("/"):
            pat = pat[1:]
            prefix -= 1
        name = path
        if prefix:
            if prefix > len(name) or pat[:prefix] != name[:prefix]:
                return False
            pat = pat[prefix:]
            name = name[prefix:]
            if not pat and not name:
                return True
        return wildmatch(pat, name, pathname=True)


def parse_line(line: str):
    """Parse one .gitignore line; return a Pattern or None for no pattern."""
    if line.endswith("\r"):
        line = line[:-1]
    if line == "" or line.startswith("#"):
        return None
    line = _trim_trailing_spaces(line)
    if line == "":
        return None
    p = line
    negative = False
    if p.startswith("!"):
        negative = True
        p = p[1:]
    must_be_dir = False
    if p.endswith("/"):
        must_be_dir = True
        p = p[:-1]
    if p == "":
        return None
    no_dir = "/" not in p
    prefix = min(simple_length(p), len(p))
    return Pattern(line, p, negative, must_be_dir, no_dir, prefix)


def parse_gitignore(text: str) -> list:
    """Parse the full text of a .gitignore file into a list of Patterns."""
    if text.startswith("﻿"):
        text = text[1:]
    patterns = []
    for line in text.split("\n"):
        pat = parse_line(line)
        if pat is not None:
            patterns.append(pat)
    return patterns
