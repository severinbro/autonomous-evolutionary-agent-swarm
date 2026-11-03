"""Semantic version parsing and comparison (node-semver 7.x, default options).

The regular expressions mirror node-semver's ``internal/re.js`` including its
"safe" quantifier limits, translated to Python semantics:
JavaScript ``\\s`` / ``trim()`` whitespace, ASCII-only ``\\d`` and an
end-of-string ``$`` (``\\Z`` in Python).
"""

import re

MAX_LENGTH = 256
MAX_SAFE_INTEGER = 2 ** 53 - 1
MAX_SAFE_BUILD_LENGTH = MAX_LENGTH - 6

# Characters matched by JavaScript's \s and removed by String.prototype.trim().
_WS_CHARS = (
    "\t\n\x0b\x0c\r \xa0 "
    + "".join(chr(c) for c in range(0x2000, 0x200B))
    + "    　﻿"
)
_WS_CLASS = "\t\n\x0b\x0c\r \xa0  -     　﻿"

# Regex building blocks (JS token -> safe Python equivalent).
S = "[" + _WS_CLASS + "]"          # \s
S_STAR = S + "{0,1}"               # safe \s*
S_PLUS = S + "{1,1}"               # safe \s+
WS_RUN = re.compile(S + "+")       # unrestricted /\s+/ (used for split/replace)
D_STAR = "[0-9]{0,%d}" % MAX_LENGTH
D_PLUS = "[0-9]{1,%d}" % MAX_LENGTH
LDN = "[a-zA-Z0-9-]"
LDN_STAR = LDN + "{0,%d}" % MAX_SAFE_BUILD_LENGTH
LDN_PLUS = LDN + "{1,%d}" % MAX_SAFE_BUILD_LENGTH
V_EQ_WS = "[v=" + _WS_CLASS + "]*"  # [v=\s]*

NUMERICIDENTIFIER = "0|[1-9]" + D_STAR
NUMERICIDENTIFIERLOOSE = D_PLUS
NONNUMERICIDENTIFIER = D_STAR + "[a-zA-Z-]" + LDN_STAR
MAINVERSION = r"({0})\.({0})\.({0})".format(NUMERICIDENTIFIER)
MAINVERSIONLOOSE = r"({0})\.({0})\.({0})".format(NUMERICIDENTIFIERLOOSE)
PRERELEASEIDENTIFIER = "(?:%s|%s)" % (NONNUMERICIDENTIFIER, NUMERICIDENTIFIER)
PRERELEASEIDENTIFIERLOOSE = "(?:%s|%s)" % (NONNUMERICIDENTIFIER, NUMERICIDENTIFIERLOOSE)
PRERELEASE = r"(?:-({0}(?:\.{0})*))".format(PRERELEASEIDENTIFIER)
PRERELEASELOOSE = r"(?:-?({0}(?:\.{0})*))".format(PRERELEASEIDENTIFIERLOOSE)
BUILDIDENTIFIER = LDN_PLUS
BUILD = r"(?:\+({0}(?:\.{0})*))".format(BUILDIDENTIFIER)
FULLPLAIN = "v?%s%s?%s?" % (MAINVERSION, PRERELEASE, BUILD)
LOOSEPLAIN = "%s%s%s?%s?" % (V_EQ_WS, MAINVERSIONLOOSE, PRERELEASELOOSE, BUILD)
GTLT = "((?:<|>)?=?)"
XRANGEIDENTIFIER = NUMERICIDENTIFIER + r"|x|X|\*"
XRANGEPLAIN = r"{ws}({x})(?:\.({x})(?:\.({x})(?:{pr})?{b}?)?)?".format(
    ws=V_EQ_WS, x=XRANGEIDENTIFIER, pr=PRERELEASE, b=BUILD)
LONETILDE = "(?:~>?)"
LONECARET = r"(?:\^)"

RE_FULL = re.compile("^" + FULLPLAIN + r"\Z")
RE_BUILD = re.compile(BUILD)
RE_XRANGE = re.compile("^" + GTLT + S_STAR + XRANGEPLAIN + r"\Z")
RE_TILDETRIM = re.compile("(" + S_STAR + ")" + LONETILDE + S_PLUS)
RE_TILDE = re.compile("^" + LONETILDE + XRANGEPLAIN + r"\Z")
RE_CARETTRIM = re.compile("(" + S_STAR + ")" + LONECARET + S_PLUS)
RE_CARET = re.compile("^" + LONECARET + XRANGEPLAIN + r"\Z")
RE_COMPARATOR = re.compile("^" + GTLT + S_STAR + "(" + FULLPLAIN + r")\Z|^\Z")
RE_COMPARATORTRIM = re.compile(
    "(" + S_STAR + ")" + GTLT + S_STAR + "(" + LOOSEPLAIN + "|" + XRANGEPLAIN + ")")
RE_HYPHENRANGE = re.compile(
    "^" + S_STAR + "(" + XRANGEPLAIN + ")" + S_PLUS + "-" + S_PLUS
    + "(" + XRANGEPLAIN + ")" + S_STAR + r"\Z")
RE_STAR = re.compile("(<|>)?=?" + S_STAR + r"\*")
RE_GTE0 = re.compile("^" + S_STAR + ">=" + S_STAR + r"0\.0\.0" + S_STAR + r"\Z")

_NUMERIC = re.compile(r"^[0-9]+\Z")


def js_trim(s):
    """String.prototype.trim()."""
    return s.strip(_WS_CHARS)


def js_split_ws(s):
    """String.prototype.split(/\\s+/)."""
    return WS_RUN.split(s)


def _js_length(s):
    """Length in UTF-16 code units, like JavaScript's String length."""
    return sum(2 if ord(c) > 0xFFFF else 1 for c in s)


class SemVer:
    """A parsed semantic version (mirrors node-semver's SemVer class)."""

    __slots__ = ("raw", "major", "minor", "patch", "prerelease", "build", "version")

    def __init__(self, version):
        if isinstance(version, SemVer):
            version = version.version
        if not isinstance(version, str):
            raise ValueError("Invalid version. Must be a string.")
        if _js_length(version) > MAX_LENGTH:
            raise ValueError("version is longer than %d characters" % MAX_LENGTH)
        m = RE_FULL.match(js_trim(version))
        if not m:
            raise ValueError("Invalid Version: %s" % version)
        self.raw = version
        self.major = int(m.group(1))
        self.minor = int(m.group(2))
        self.patch = int(m.group(3))
        if self.major > MAX_SAFE_INTEGER:
            raise ValueError("Invalid major version")
        if self.minor > MAX_SAFE_INTEGER:
            raise ValueError("Invalid minor version")
        if self.patch > MAX_SAFE_INTEGER:
            raise ValueError("Invalid patch version")
        pre = m.group(4)
        self.prerelease = [] if not pre else [_pre_id(i) for i in pre.split(".")]
        b = m.group(5)
        self.build = b.split(".") if b else []
        self.version = "%d.%d.%d" % (self.major, self.minor, self.patch)
        if self.prerelease:
            self.version += "-" + ".".join(str(i) for i in self.prerelease)

    def compare(self, other):
        if not isinstance(other, SemVer):
            if isinstance(other, str) and other == self.version:
                return 0
            other = SemVer(other)
        if other.version == self.version:
            return 0
        return self.compare_main(other) or self.compare_pre(other)

    def compare_main(self, other):
        for a, b in ((self.major, other.major), (self.minor, other.minor),
                     (self.patch, other.patch)):
            if a < b:
                return -1
            if a > b:
                return 1
        return 0

    def compare_pre(self, other):
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
            if not (type(a) is type(b) and a == b):
                return compare_identifiers(a, b)
            i += 1

    def __repr__(self):
        return "SemVer(%r)" % self.version


def _pre_id(ident):
    if _NUMERIC.match(ident):
        num = int(ident)
        if 0 <= num < MAX_SAFE_INTEGER:
            return num
    return ident


def compare_identifiers(a, b):
    """node-semver's compareIdentifiers (numeric ids sort below alphanumeric)."""
    anum = bool(_NUMERIC.match(str(a)))
    bnum = bool(_NUMERIC.match(str(b)))
    if anum and bnum:
        # JavaScript converts with unary +, i.e. to an IEEE double.
        a, b = float(a), float(b)
        if a == b:
            return 0
        return -1 if a < b else 1
    if anum and not bnum:
        return -1
    if bnum and not anum:
        return 1
    a, b = str(a), str(b)
    if a == b:
        return 0
    return -1 if a < b else 1


def parse(version):
    """Return a SemVer, or None if ``version`` is not a valid version."""
    if isinstance(version, SemVer):
        return version
    try:
        return SemVer(version)
    except ValueError:
        return None


def valid(text):
    """Like ``semver.valid``: the normalized version, or None."""
    v = parse(text)
    return v.version if v is not None else None


def compare(a, b):
    """Like ``semver.compare``: -1, 0 or 1. Raises ValueError if invalid."""
    return SemVer(a).compare(SemVer(b))
