"""Cron expression parser following crontab(5) (Vixie cron / cronie).

Supported syntax per field: ``*``, numbers, ranges ``a-b``, lists
``a,b,c``, steps ``*/n`` and ``a-b/n``, and (for month / day-of-week)
three-letter case-insensitive names, which may also appear in ranges and
lists.  Day-of-week accepts 0-7 where both 0 and 7 mean Sunday.

Special strings: @yearly, @annually, @monthly, @weekly, @daily,
@midnight, @hourly.  @reboot is not supported.

Day matching follows cron's rule: if either the day-of-month or the
day-of-week field starts with ``*``, a day must match both fields;
otherwise a day matches if it matches either field.
"""

from dataclasses import dataclass

MONTH_NAMES = ("jan", "feb", "mar", "apr", "may", "jun",
               "jul", "aug", "sep", "oct", "nov", "dec")
DOW_NAMES = ("sun", "mon", "tue", "wed", "thu", "fri", "sat")

SHORTCUTS = {
    "@yearly": "0 0 1 1 *",
    "@annually": "0 0 1 1 *",
    "@monthly": "0 0 1 * *",
    "@weekly": "0 0 * * 0",
    "@daily": "0 0 * * *",
    "@midnight": "0 0 * * *",
    "@hourly": "0 * * * *",
}

# (name, low, high, names, names_offset)
_FIELDS = (
    ("minute", 0, 59, None, 0),
    ("hour", 0, 23, None, 0),
    ("day of month", 1, 31, None, 0),
    ("month", 1, 12, MONTH_NAMES, 1),
    ("day of week", 0, 7, DOW_NAMES, 0),
)


@dataclass(frozen=True)
class Schedule:
    minutes: frozenset
    hours: frozenset
    days_of_month: frozenset
    months: frozenset
    days_of_week: frozenset  # 0 = Sunday ... 6 = Saturday (7 folded into 0)
    dom_star: bool
    dow_star: bool
    expr: str = ""

    def matches_day(self, year, month, day, weekday_sun0):
        """True if the given calendar day is a firing day."""
        if month not in self.months:
            return False
        dom_ok = day in self.days_of_month
        dow_ok = weekday_sun0 in self.days_of_week
        if self.dom_star or self.dow_star:
            return dom_ok and dow_ok
        return dom_ok or dow_ok


def _parse_value(token, low, high, names, offset, field):
    if not token:
        raise ValueError(f"empty value in {field} field")
    if token.isascii() and token.isdigit():
        value = int(token)
    elif names is not None and token.isascii() and token.isalpha():
        lowered = token.lower()
        if lowered not in names:
            raise ValueError(f"unknown name {token!r} in {field} field")
        value = names.index(lowered) + offset
    else:
        raise ValueError(f"invalid value {token!r} in {field} field")
    if value < low or value > high:
        raise ValueError(f"value {value} out of range {low}-{high} in {field} field")
    return value


def _parse_step(token, field):
    if not (token and token.isascii() and token.isdigit()):
        raise ValueError(f"invalid step {token!r} in {field} field")
    step = int(token)
    if step == 0:
        raise ValueError(f"step of zero in {field} field")
    return step


def _parse_field(text, low, high, names, offset, field):
    values = set()
    for item in text.split(","):
        if not item:
            raise ValueError(f"empty list element in {field} field")
        if "/" in item:
            range_part, step_text = item.split("/", 1)
            step = _parse_step(step_text, field)
        else:
            range_part, step = item, None
        if range_part == "*":
            start, end = low, high
        elif "-" in range_part:
            first, last = range_part.split("-", 1)
            start = _parse_value(first, low, high, names, offset, field)
            end = _parse_value(last, low, high, names, offset, field)
            if start > end:
                raise ValueError(f"reversed range {range_part!r} in {field} field")
        else:
            # A single value; crontab(5) only allows steps after a range or '*'.
            if step is not None:
                raise ValueError(f"step without a range in {field} field: {item!r}")
            start = end = _parse_value(range_part, low, high, names, offset, field)
        values.update(range(start, end + 1, step or 1))
    return values


def parse(expr):
    """Parse a cron expression into a Schedule; raise ValueError if invalid."""
    if not isinstance(expr, str):
        raise ValueError("cron expression must be a string")
    original = expr
    text = expr.strip()
    if text.startswith("@"):
        if text not in SHORTCUTS:
            raise ValueError(f"unsupported special string {text!r}")
        text = SHORTCUTS[text]
    parts = text.split()
    if len(parts) != 5:
        raise ValueError(f"expected 5 fields, got {len(parts)}: {original!r}")
    sets = []
    for part, (field, low, high, names, offset) in zip(parts, _FIELDS):
        sets.append(_parse_field(part, low, high, names, offset, field))
    dow = sets[4]
    if 7 in dow:
        dow.discard(7)
        dow.add(0)
    return Schedule(
        minutes=frozenset(sets[0]),
        hours=frozenset(sets[1]),
        days_of_month=frozenset(sets[2]),
        months=frozenset(sets[3]),
        days_of_week=frozenset(dow),
        dom_star=parts[2].startswith("*"),
        dow_star=parts[4].startswith("*"),
        expr=original,
    )
