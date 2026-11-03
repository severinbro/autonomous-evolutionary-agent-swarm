"""Semantic version ranges, mirroring node-semver 7.x with default options
(not loose, includePrerelease off).

Public API:
    satisfies(version, range_text) -> bool
    max_satisfying(versions, range_text) -> str | None
    Range, Comparator (internal helpers, exposed for testing)

The range desugaring follows node-semver's regex-driven pipeline step by
step: hyphen ranges, comparator/tilde/caret whitespace trimming, build
stripping, caret, tilde, x-range and star replacement, ``>=0.0.0`` -> ``*``.
"""

import re

from .version import SemVer, parse, js_trim

# JavaScript's \s character class (WhiteSpace + LineTerminator).
_WS_CHARS = (
    "\\t\\n\\x0b\\x0c\\r \\u00a0\\u1680\\u2000-\\u200a"
    "\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff"
)
S = "[" + _WS_CHARS + "]"

# node-semver 7.x matches with `safeRe`, which caps unbounded quantifiers:
# \d* -> \d{0,256}, \d+ -> \d{1,256}, [a-zA-Z0-9-]* -> {0,250}, + -> {1,250}
# (MAX_LENGTH = 256, MAX_SAFE_BUILD_LENGTH = MAX_LENGTH - 6). Over-long
# tokens therefore fail to match exactly as they do in node.
NUMERICIDENTIFIER = r"0|[1-9][0-9]{0,256}"
NUMERICIDENTIFIERLOOSE = r"[0-9]{1,256}"
NONNUMERICIDENTIFIER = r"[0-9]{0,256}[a-zA-Z-][a-zA-Z0-9-]{0,250}"
MAINVERSION = r"(%s)\.(%s)\.(%s)" % ((NUMERICIDENTIFIER,) * 3)
MAINVERSIONLOOSE = r"(%s)\.(%s)\.(%s)" % ((NUMERICIDENTIFIERLOOSE,) * 3)
PRERELEASEIDENTIFIER = r"(?:%s|%s)" % (NUMERICIDENTIFIER, NONNUMERICIDENTIFIER)
PRERELEASEIDENTIFIERLOOSE = r"(?:%s|%s)" % (NUMERICIDENTIFIERLOOSE, NONNUMERICIDENTIFIER)
PRERELEASE = r"(?:-(%s(?:\.%s)*))" % (PRERELEASEIDENTIFIER, PRERELEASEIDENTIFIER)
PRERELEASELOOSE = r"(?:-?(%s(?:\.%s)*))" % (PRERELEASEIDENTIFIERLOOSE, PRERELEASEIDENTIFIERLOOSE)
BUILDIDENTIFIER = r"[a-zA-Z0-9-]{1,250}"
BUILD = r"(?:\+(%s(?:\.%s)*))" % (BUILDIDENTIFIER, BUILDIDENTIFIER)
FULLPLAIN = r"v?%s%s?%s?" % (MAINVERSION, PRERELEASE, BUILD)
LOOSEPLAIN = r"[v=%s]*%s%s?%s?" % (_WS_CHARS, MAINVERSIONLOOSE, PRERELEASELOOSE, BUILD)
GTLT = r"((?:<|>)?=?)"
XRANGEIDENTIFIER = r"%s|x|X|\*" % NUMERICIDENTIFIER
XRANGEPLAIN = (
    r"[v=%s]*(%s)(?:\.(%s)(?:\.(%s)(?:%s)?%s?)?)?"
    % (_WS_CHARS, XRANGEIDENTIFIER, XRANGEIDENTIFIER, XRANGEIDENTIFIER, PRERELEASE, BUILD)
)

# JavaScript's `$` (without the m flag) only matches at the very end: use \Z.
XRANGE_RE = re.compile(r"^%s%s*%s\Z" % (GTLT, S, XRANGEPLAIN))
TILDE_RE = re.compile(r"^(?:~>?)%s\Z" % XRANGEPLAIN)
CARET_RE = re.compile(r"^(?:\^)%s\Z" % XRANGEPLAIN)
COMPARATOR_RE = re.compile(r"^%s%s*(%s)\Z|^\Z" % (GTLT, S, FULLPLAIN))
HYPHENRANGE_RE = re.compile(
    r"^%s*(%s)%s+-%s+(%s)%s*\Z" % (S, XRANGEPLAIN, S, S, XRANGEPLAIN, S)
)
COMPARATORTRIM_RE = re.compile(
    r"(%s*)%s%s*(%s|%s)" % (S, GTLT, S, LOOSEPLAIN, XRANGEPLAIN)
)
TILDETRIM_RE = re.compile(r"(%s*)(?:~>?)%s+" % (S, S))
CARETTRIM_RE = re.compile(r"(%s*)(?:\^)%s+" % (S, S))
STAR_RE = re.compile(r"(<|>)?=?%s*\*" % S)
GTE0_RE = re.compile(r"^%s*>=%s*0\.0\.0%s*\Z" % (S, S, S))
BUILD_RE = re.compile(BUILD)
WS_RUN_RE = re.compile(S + "+")

MAX_SAFE_INTEGER = 2 ** 53 - 1


def _js_split_ws(text):
    """JavaScript ``text.split(/\\s+/)``."""
    return WS_RUN_RE.split(text)


def _is_x(ident):
    return not ident or ident.lower() == "x" or ident == "*"


def _inc(num):
    """JavaScript ``+num + 1`` rendered back to a string."""
    value = int(num) + 1
    if value > MAX_SAFE_INTEGER:
        # JS would lose precision / switch to exponent notation; any such
        # number is rejected later as an invalid version component anyway.
        return repr(float(value))
    return str(value)


# ---------------------------------------------------------------- hyphen

def _hyphen_replace(m):
    frm, f_major, f_minor, f_patch, f_pre = m.group(1, 2, 3, 4, 5)
    to, t_major, t_minor, t_patch, t_pre = m.group(7, 8, 9, 10, 11)

    if _is_x(f_major):
        frm = ""
    elif _is_x(f_minor):
        frm = ">=%s.0.0" % f_major
    elif _is_x(f_patch):
        frm = ">=%s.%s.0" % (f_major, f_minor)
    else:
        frm = ">=%s" % frm

    if _is_x(t_major):
        to = ""
    elif _is_x(t_minor):
        to = "<%s.0.0-0" % _inc(t_major)
    elif _is_x(t_patch):
        to = "<%s.%s.0-0" % (t_major, _inc(t_minor))
    elif t_pre:
        to = "<=%s.%s.%s-%s" % (t_major, t_minor, t_patch, t_pre)
    else:
        to = "<=%s" % to

    return js_trim("%s %s" % (frm, to))


# ---------------------------------------------------------------- caret / tilde

def _replace_caret(comp):
    def repl(m):
        major, minor, patch, pre = m.group(1, 2, 3, 4)
        if _is_x(major):
            return ""
        if _is_x(minor):
            return ">=%s.0.0 <%s.0.0-0" % (major, _inc(major))
        if _is_x(patch):
            if major == "0":
                return ">=%s.%s.0 <%s.%s.0-0" % (major, minor, major, _inc(minor))
            return ">=%s.%s.0 <%s.0.0-0" % (major, minor, _inc(major))
        low = "%s.%s.%s" % (major, minor, patch)
        if pre:
            low += "-" + pre
        if major == "0":
            if minor == "0":
                return ">=%s <%s.%s.%s-0" % (low, major, minor, _inc(patch))
            return ">=%s <%s.%s.0-0" % (low, major, _inc(minor))
        return ">=%s <%s.0.0-0" % (low, _inc(major))

    return CARET_RE.sub(repl, comp, count=1)


def _replace_carets(comp):
    return " ".join(_replace_caret(c) for c in _js_split_ws(js_trim(comp)))


def _replace_tilde(comp):
    def repl(m):
        major, minor, patch, pre = m.group(1, 2, 3, 4)
        if _is_x(major):
            return ""
        if _is_x(minor):
            return ">=%s.0.0 <%s.0.0-0" % (major, _inc(major))
        if _is_x(patch):
            return ">=%s.%s.0 <%s.%s.0-0" % (major, minor, major, _inc(minor))
        if pre:
            return ">=%s.%s.%s-%s <%s.%s.0-0" % (major, minor, patch, pre, major, _inc(minor))
        return ">=%s.%s.%s <%s.%s.0-0" % (major, minor, patch, major, _inc(minor))

    return TILDE_RE.sub(repl, comp, count=1)


def _replace_tildes(comp):
    return " ".join(_replace_tilde(c) for c in _js_split_ws(js_trim(comp)))


# ---------------------------------------------------------------- x-ranges

def _replace_xrange(comp):
    comp = js_trim(comp)

    def repl(m):
        ret = m.group(0)
        gtlt, major, minor, patch = m.group(1, 2, 3, 4)
        x_major = _is_x(major)
        x_minor = x_major or _is_x(minor)
        x_patch = x_minor or _is_x(patch)
        any_x = x_patch

        if gtlt == "=" and any_x:
            gtlt = ""
        pre = ""

        if x_major:
            if gtlt in (">", "<"):
                ret = "<0.0.0-0"
            else:
                ret = "*"
        elif gtlt and any_x:
            if x_minor:
                minor = "0"
            patch = "0"
            if gtlt == ">":
                gtlt = ">="
                if x_minor:
                    major = _inc(major)
                    minor = "0"
                    patch = "0"
                else:
                    minor = _inc(minor)
                    patch = "0"
            elif gtlt == "<=":
                gtlt = "<"
                if x_minor:
                    major = _inc(major)
                else:
                    minor = _inc(minor)
            if gtlt == "<":
                pre = "-0"
            ret = "%s%s.%s.%s%s" % (gtlt, major, minor, patch, pre)
        elif x_minor:
            ret = ">=%s.0.0%s <%s.0.0-0" % (major, pre, _inc(major))
        elif x_patch:
            ret = ">=%s.%s.0%s <%s.%s.0-0" % (major, minor, pre, major, _inc(minor))
        return ret

    return XRANGE_RE.sub(repl, comp, count=1)


def _replace_xranges(comp):
    return " ".join(_replace_xrange(c) for c in _js_split_ws(comp))


def _replace_stars(comp):
    return STAR_RE.sub("", js_trim(comp), count=1)


def _replace_gte0(comp):
    return GTE0_RE.sub("", js_trim(comp), count=1)


def _parse_comparator(comp):
    comp = BUILD_RE.sub("", comp, count=1)
    comp = _replace_carets(comp)
    comp = _replace_tildes(comp)
    comp = _replace_xranges(comp)
    comp = _replace_stars(comp)
    return comp


# ---------------------------------------------------------------- Comparator

class Comparator:
    """A single ``<op><version>`` comparator; ``semver is None`` means ANY."""

    __slots__ = ("operator", "semver", "value")

    def __init__(self, comp):
        comp = " ".join(_js_split_ws(js_trim(comp)))
        m = COMPARATOR_RE.match(comp)
        if m is None:
            raise ValueError("Invalid comparator: %s" % comp)
        operator = m.group(1) or ""
        if operator == "=":
            operator = ""
        self.operator = operator
        if not m.group(2):
            self.semver = None
            self.value = ""
        else:
            sv = parse(m.group(2))
            if sv is None:
                raise ValueError("Invalid comparator version: %s" % m.group(2))
            self.semver = sv
            self.value = operator + sv.version

    def test(self, version):
        if self.semver is None:
            return True
        c = version.compare(self.semver)
        op = self.operator
        if op == "":
            return c == 0
        if op == ">":
            return c > 0
        if op == ">=":
            return c >= 0
        if op == "<":
            return c < 0
        if op == "<=":
            return c <= 0
        raise ValueError("Invalid operator: %s" % op)

    def __repr__(self):
        return "Comparator(%r)" % self.value


def _is_null_set(c):
    return c.value == "<0.0.0-0"


def _is_any(c):
    return c.value == ""


# ---------------------------------------------------------------- Range

class Range:
    """A parsed range: a list (||) of lists (AND) of Comparators."""

    def __init__(self, range_text):
        if not isinstance(range_text, str):
            raise TypeError("Invalid range: must be a string")
        self.raw = WS_RUN_RE.sub(" ", js_trim(range_text))
        sets = [self._parse_range(js_trim(r)) for r in self.raw.split("||")]
        sets = [c for c in sets if c]
        if not sets:
            raise ValueError("Invalid SemVer Range: %s" % self.raw)
        if len(sets) > 1:
            first = sets[0]
            sets = [c for c in sets if not _is_null_set(c[0])]
            if not sets:
                sets = [first]
            elif len(sets) > 1:
                for c in sets:
                    if len(c) == 1 and _is_any(c[0]):
                        sets = [c]
                        break
        self.set = sets

    @staticmethod
    def _parse_range(rng):
        rng = HYPHENRANGE_RE.sub(_hyphen_replace, rng, count=1)
        rng = COMPARATORTRIM_RE.sub(r"\1\2\3", rng)
        rng = TILDETRIM_RE.sub(r"\1~", rng)
        rng = CARETTRIM_RE.sub(r"\1^", rng)

        joined = " ".join(_parse_comparator(c) for c in rng.split(" "))
        range_list = [_replace_gte0(c) for c in _js_split_ws(joined)]

        comparators = [Comparator(c) for c in range_list]
        range_map = {}
        for comp in comparators:
            if _is_null_set(comp):
                return [comp]
            # JS Map.set keeps the original insertion position on overwrite.
            range_map[comp.value] = comp
        if len(range_map) > 1 and "" in range_map:
            del range_map[""]
        return list(range_map.values())

    def test(self, version):
        if not version:
            return False
        if not isinstance(version, SemVer):
            version = parse(version)
            if version is None:
                return False
        return any(_test_set(s, version) for s in self.set)


def _test_set(comparators, version):
    for c in comparators:
        if not c.test(version):
            return False
    if version.prerelease:
        # Prereleases only match when some comparator in the set has a
        # prerelease on the same [major, minor, patch] tuple.
        for c in comparators:
            if c.semver is None:
                continue
            allowed = c.semver
            if allowed.prerelease and (
                allowed.major == version.major
                and allowed.minor == version.minor
                and allowed.patch == version.patch
            ):
                return True
        return False
    return True


def _make_range(range_text):
    try:
        return Range(range_text)
    except (TypeError, ValueError):
        return None


def satisfies(version, range_text):
    """Like semver.satisfies(version, range): False for invalid input."""
    rng = _make_range(range_text)
    if rng is None:
        return False
    return rng.test(version)


def max_satisfying(versions, range_text):
    """Like semver.maxSatisfying: highest satisfying version, as given, or None."""
    rng = _make_range(range_text)
    if rng is None:
        return None
    best = None
    best_sv = None
    for v in versions:
        if rng.test(v):
            sv = parse(v)
            if best is None or best_sv.compare(sv) == -1:
                best = v
                best_sv = sv
    return best
