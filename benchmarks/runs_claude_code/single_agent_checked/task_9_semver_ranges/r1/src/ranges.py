"""npm-compatible semver ranges (node-semver 7.x, default options).

Mirrors node-semver's Range/Comparator desugaring: hyphen ranges, X-ranges,
tilde, caret, star, ``||`` unions and whitespace handling, then evaluates the
resulting comparator sets with the default prerelease exclusion rule.
"""

try:
    from . import version as _v
except ImportError:  # pragma: no cover - allows running as a plain module
    import version as _v  # type: ignore

SemVer = _v.SemVer
js_trim = _v.js_trim
js_split_ws = _v.js_split_ws


class _Any:
    """Sentinel for the comparator that matches every version."""

    def __repr__(self):
        return "ANY"


ANY = _Any()
NULL_SET = "<0.0.0-0"


def _is_x(ident):
    return not ident or ident.lower() == "x" or ident == "*"


class Comparator:
    __slots__ = ("operator", "semver", "value")

    def __init__(self, comp):
        comp = " ".join(js_split_ws(js_trim(comp)))
        m = _v.RE_COMPARATOR.match(comp)
        if not m:
            raise ValueError("Invalid comparator: %s" % comp)
        op = m.group(1) if m.group(1) is not None else ""
        if op == "=":
            op = ""
        self.operator = op
        if not m.group(2):
            self.semver = ANY
            self.value = ""
        else:
            self.semver = SemVer(m.group(2))
            self.value = self.operator + self.semver.version

    def test(self, version):
        if self.semver is ANY or version is ANY:
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
        raise ValueError("Invalid operator: %s" % op)  # pragma: no cover

    def __repr__(self):
        return "Comparator(%r)" % self.value


# --- desugaring steps -------------------------------------------------------

def _hyphen_replace(m):
    (frm, f_maj, f_min, f_pat, f_pr, _fb,
     to, t_maj, t_min, t_pat, t_pr, _tb) = m.groups()
    if _is_x(f_maj):
        frm = ""
    elif _is_x(f_min):
        frm = ">=%s.0.0" % f_maj
    elif _is_x(f_pat):
        frm = ">=%s.%s.0" % (f_maj, f_min)
    else:
        frm = ">=" + frm

    if _is_x(t_maj):
        to = ""
    elif _is_x(t_min):
        to = "<%d.0.0-0" % (int(t_maj) + 1)
    elif _is_x(t_pat):
        to = "<%s.%d.0-0" % (t_maj, int(t_min) + 1)
    elif t_pr:
        to = "<=%s.%s.%s-%s" % (t_maj, t_min, t_pat, t_pr)
    else:
        to = "<=" + to
    return js_trim("%s %s" % (frm, to))


def _replace_caret(comp):
    def repl(m):
        M, mi, p, pr = m.group(1), m.group(2), m.group(3), m.group(4)
        if _is_x(M):
            return ""
        if _is_x(mi):
            return ">=%s.0.0 <%d.0.0-0" % (M, int(M) + 1)
        if _is_x(p):
            if M == "0":
                return ">=%s.%s.0 <%s.%d.0-0" % (M, mi, M, int(mi) + 1)
            return ">=%s.%s.0 <%d.0.0-0" % (M, mi, int(M) + 1)
        low = ">=%s.%s.%s" % (M, mi, p) + ("-" + pr if pr else "")
        if M == "0":
            if mi == "0":
                return "%s <%s.%s.%d-0" % (low, M, mi, int(p) + 1)
            return "%s <%s.%d.0-0" % (low, M, int(mi) + 1)
        return "%s <%d.0.0-0" % (low, int(M) + 1)
    return _v.RE_CARET.sub(repl, comp, count=1)


def _replace_carets(comp):
    return " ".join(_replace_caret(c) for c in js_split_ws(js_trim(comp)))


def _replace_tilde(comp):
    def repl(m):
        M, mi, p, pr = m.group(1), m.group(2), m.group(3), m.group(4)
        if _is_x(M):
            return ""
        if _is_x(mi):
            return ">=%s.0.0 <%d.0.0-0" % (M, int(M) + 1)
        if _is_x(p):
            return ">=%s.%s.0 <%s.%d.0-0" % (M, mi, M, int(mi) + 1)
        low = ">=%s.%s.%s" % (M, mi, p) + ("-" + pr if pr else "")
        return "%s <%s.%d.0-0" % (low, M, int(mi) + 1)
    return _v.RE_TILDE.sub(repl, comp, count=1)


def _replace_tildes(comp):
    return " ".join(_replace_tilde(c) for c in js_split_ws(js_trim(comp)))


def _replace_xrange(comp):
    comp = js_trim(comp)

    def repl(m):
        ret = m.group(0)
        gtlt, M, mi, p = m.group(1), m.group(2), m.group(3), m.group(4)
        x_maj = _is_x(M)
        x_min = x_maj or _is_x(mi)
        x_pat = x_min or _is_x(p)
        any_x = x_pat
        if gtlt == "=" and any_x:
            gtlt = ""
        pr = ""
        if x_maj:
            if gtlt in (">", "<"):
                ret = "<0.0.0-0"
            else:
                ret = "*"
        elif gtlt and any_x:
            if x_min:
                mi = 0
            p = 0
            if gtlt == ">":
                gtlt = ">="
                if x_min:
                    M = int(M) + 1
                    mi = 0
                    p = 0
                else:
                    mi = int(mi) + 1
                    p = 0
            elif gtlt == "<=":
                gtlt = "<"
                if x_min:
                    M = int(M) + 1
                else:
                    mi = int(mi) + 1
            if gtlt == "<":
                pr = "-0"
            ret = "%s%s.%s.%s%s" % (gtlt, M, mi, p, pr)
        elif x_min:
            ret = ">=%s.0.0%s <%d.0.0-0" % (M, pr, int(M) + 1)
        elif x_pat:
            ret = ">=%s.%s.0%s <%s.%d.0-0" % (M, mi, pr, M, int(mi) + 1)
        return ret

    return _v.RE_XRANGE.sub(repl, comp, count=1)


def _replace_xranges(comp):
    return " ".join(_replace_xrange(c) for c in js_split_ws(comp))


def _replace_stars(comp):
    return _v.RE_STAR.sub("", js_trim(comp), count=1)


def _replace_gte0(comp):
    return _v.RE_GTE0.sub("", js_trim(comp), count=1)


def _parse_comparator(comp):
    comp = _v.RE_BUILD.sub("", comp, count=1)
    comp = _replace_carets(comp)
    comp = _replace_tildes(comp)
    comp = _replace_xranges(comp)
    comp = _replace_stars(comp)
    return comp


def _grp(m, i):
    s = m.group(i)
    return s if s is not None else ""


def _parse_range_part(rng):
    rng = _v.RE_HYPHENRANGE.sub(_hyphen_replace, rng, count=1)
    rng = _v.RE_COMPARATORTRIM.sub(
        lambda m: _grp(m, 1) + _grp(m, 2) + _grp(m, 3), rng)
    rng = _v.RE_TILDETRIM.sub(lambda m: _grp(m, 1) + "~", rng)
    rng = _v.RE_CARETTRIM.sub(lambda m: _grp(m, 1) + "^", rng)

    joined = " ".join(_parse_comparator(c) for c in rng.split(" "))
    range_list = [_replace_gte0(c) for c in js_split_ws(joined)]
    comparators = [Comparator(c) for c in range_list]

    range_map = {}
    for comp in comparators:
        if comp.value == NULL_SET:
            return [comp]
        range_map[comp.value] = comp
    if len(range_map) > 1 and "" in range_map:
        del range_map[""]
    return list(range_map.values())


class Range:
    """A parsed range: a union (``||``) of comparator intersections."""

    def __init__(self, range_text):
        if not isinstance(range_text, str):
            raise ValueError("Invalid SemVer Range")
        self.raw = _v.WS_RUN.sub(" ", js_trim(range_text))
        sets = [_parse_range_part(js_trim(r)) for r in self.raw.split("||")]
        sets = [c for c in sets if c]
        if not sets:
            raise ValueError("Invalid SemVer Range: %s" % self.raw)
        if len(sets) > 1:
            first = sets[0]
            sets = [c for c in sets if c[0].value != NULL_SET]
            if not sets:
                sets = [first]
            elif len(sets) > 1:
                for c in sets:
                    if len(c) == 1 and c[0].value == "":
                        sets = [c]
                        break
        self.set = sets

    def test(self, version):
        if not version:
            return False
        if not isinstance(version, SemVer):
            try:
                version = SemVer(version)
            except ValueError:
                return False
        return any(_test_set(s, version) for s in self.set)


def _test_set(comparators, version):
    for comp in comparators:
        if not comp.test(version):
            return False
    if version.prerelease:
        # A prerelease only matches if some comparator in the set opts in to
        # prereleases of the same [major, minor, patch] tuple.
        for comp in comparators:
            if comp.semver is ANY:
                continue
            if comp.semver.prerelease:
                allowed = comp.semver
                if (allowed.major == version.major and allowed.minor == version.minor
                        and allowed.patch == version.patch):
                    return True
        return False
    return True


def satisfies(version, range_text):
    """Like ``semver.satisfies``; False for an invalid version or range."""
    try:
        rng = Range(range_text)
    except ValueError:
        return False
    return rng.test(version)


def max_satisfying(versions, range_text):
    """Like ``semver.maxSatisfying``: highest satisfying version, as given."""
    try:
        rng = Range(range_text)
    except ValueError:
        return None
    best = None
    best_sv = None
    for v in versions:
        if rng.test(v):
            if not best or best_sv.compare(v) == -1:
                best = v
                best_sv = SemVer(best)
    return best
