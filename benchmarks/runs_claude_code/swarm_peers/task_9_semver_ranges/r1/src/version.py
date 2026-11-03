"""Semantic version parsing and comparison, mirroring node-semver 7.x (strict mode).

Public API:
    valid(text) -> str | None
    compare(a, b) -> int            (raises ValueError on invalid input)
    parse(text) -> SemVer | None
    SemVer                          (major, minor, patch, prerelease, build, version, compare())
    compare_identifiers(a, b) -> int
    compare_parsed(a, b) -> int
"""

import functools
import re

MAX_LENGTH = 256
MAX_SAFE_INTEGER = 2 ** 53 - 1

# Characters removed by JavaScript's String.prototype.trim():
# WhiteSpace (TAB, VT, FF, SP, NBSP, ZWNBSP, Unicode "Zs") and LineTerminator.
JS_WHITESPACE = (
    "\u0009\u000b\u000c  ﻿"
    "\u000a\u000d  "
    "            "
    "  　"
)

_NUMERIC_ID = r"0|[1-9][0-9]*"
_NON_NUMERIC_ID = r"[0-9]*[a-zA-Z-][a-zA-Z0-9-]*"
_PRERELEASE_ID = r"(?:%s|%s)" % (_NUMERIC_ID, _NON_NUMERIC_ID)
_BUILD_ID = r"[a-zA-Z0-9-]+"

FULL_RE = re.compile(
    r"v?(%s)\.(%s)\.(%s)"
    r"(?:-(%s(?:\.%s)*))?"
    r"(?:\+(%s(?:\.%s)*))?"
    % (_NUMERIC_ID, _NUMERIC_ID, _NUMERIC_ID,
       _PRERELEASE_ID, _PRERELEASE_ID, _BUILD_ID, _BUILD_ID),
    re.ASCII,
)

_NUMERIC_RE = re.compile(r"[0-9]+", re.ASCII)


def js_trim(text):
    """Equivalent of JavaScript String.prototype.trim()."""
    return text.strip(JS_WHITESPACE)


def js_length(text):
    """Length of a string as JavaScript counts it (UTF-16 code units)."""
    return len(text.encode("utf-16-le", "surrogatepass")) // 2


def _is_numeric(ident):
    return _NUMERIC_RE.fullmatch(str(ident)) is not None


def compare_identifiers(a, b):
    """node-semver compareIdentifiers: numeric ids sort before alphanumeric ones."""
    anum = _is_numeric(a)
    bnum = _is_numeric(b)
    if anum and bnum:
        # JavaScript converts with unary +, i.e. to an IEEE double.
        a = float(a)
        b = float(b)
    else:
        a = str(a) if not isinstance(a, str) else a
        b = str(b) if not isinstance(b, str) else b
    if a == b:
        return 0
    if anum and not bnum:
        return -1
    if bnum and not anum:
        return 1
    if anum and bnum:
        return -1 if a < b else 1
    # JS string comparison is by UTF-16 code units; ids are ASCII so this matches.
    return -1 if a < b else 1


@functools.total_ordering
class SemVer:
    """A parsed semantic version (node-semver SemVer, default options)."""

    __slots__ = ("major", "minor", "patch", "prerelease", "build", "raw")

    def __init__(self, version):
        if isinstance(version, SemVer):
            version = version.version
        if not isinstance(version, str):
            raise TypeError("Invalid version. Must be a string. Got type %r" % type(version).__name__)
        if js_length(version) > MAX_LENGTH:
            raise ValueError("version is longer than %d characters" % MAX_LENGTH)
        m = FULL_RE.fullmatch(js_trim(version))
        if m is None:
            raise ValueError("Invalid Version: %s" % version)
        self.raw = version
        major, minor, patch = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if major > MAX_SAFE_INTEGER:
            raise ValueError("Invalid major version")
        if minor > MAX_SAFE_INTEGER:
            raise ValueError("Invalid minor version")
        if patch > MAX_SAFE_INTEGER:
            raise ValueError("Invalid patch version")
        self.major, self.minor, self.patch = major, minor, patch
        pre = m.group(4)
        if pre is None:
            self.prerelease = ()
        else:
            ids = []
            for ident in pre.split("."):
                if _NUMERIC_RE.fullmatch(ident):
                    num = int(ident)
                    if 0 <= num < MAX_SAFE_INTEGER:
                        ids.append(num)
                        continue
                ids.append(ident)
            self.prerelease = tuple(ids)
        build = m.group(5)
        self.build = tuple(build.split(".")) if build is not None else ()

    @property
    def version(self):
        v = "%d.%d.%d" % (self.major, self.minor, self.patch)
        if self.prerelease:
            v += "-" + ".".join(str(x) for x in self.prerelease)
        return v

    def __str__(self):
        return self.version

    def __repr__(self):
        return "SemVer(%r)" % self.version

    def compare_main(self, other):
        other = _coerce(other)
        return (compare_identifiers(self.major, other.major)
                or compare_identifiers(self.minor, other.minor)
                or compare_identifiers(self.patch, other.patch))

    def compare_pre(self, other):
        other = _coerce(other)
        if self.prerelease and not other.prerelease:
            return -1
        if not self.prerelease and other.prerelease:
            return 1
        if not self.prerelease and not other.prerelease:
            return 0
        i = 0
        while True:
            a = self.prerelease[i] if i < len(self.prerelease) else None
            b = other.prerelease[i] if i < len(other.prerelease) else None
            if a is None and b is None:
                return 0
            if b is None:
                return 1
            if a is None:
                return -1
            if a != b:
                return compare_identifiers(a, b)
            i += 1

    def compare(self, other):
        """-1, 0 or 1 by precedence (build metadata ignored)."""
        other = _coerce(other)
        if other.version == self.version:
            return 0
        return self.compare_main(other) or self.compare_pre(other)

    def __eq__(self, other):
        if not isinstance(other, SemVer):
            return NotImplemented
        return self.compare(other) == 0

    def __lt__(self, other):
        if not isinstance(other, SemVer):
            return NotImplemented
        return self.compare(other) < 0

    def __hash__(self):
        return hash(self.version)


def _coerce(value):
    return value if isinstance(value, SemVer) else SemVer(value)


def parse(text):
    """Return a SemVer for ``text`` or None when it is not a valid version."""
    if isinstance(text, SemVer):
        return text
    try:
        return SemVer(text)
    except (TypeError, ValueError):
        return None


def valid(text):
    """Like semver.valid(): normalized version string or None."""
    v = parse(text)
    return v.version if v is not None else None


def compare(a, b):
    """Like semver.compare(): -1, 0 or 1. Raises ValueError for invalid versions."""
    try:
        va = _coerce(a)
        vb = _coerce(b)
    except TypeError as exc:
        raise ValueError(str(exc)) from None
    return va.compare(vb)


def compare_parsed(a, b):
    """Compare two SemVer instances."""
    return a.compare(b)
