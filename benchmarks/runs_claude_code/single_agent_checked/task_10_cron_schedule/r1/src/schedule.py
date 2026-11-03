"""Next-fire computation for cron schedules (naive datetimes)."""

from datetime import date, datetime, timedelta

from .parser import Schedule, parse

# The Gregorian calendar (including weekdays) repeats every 400 years, so a
# schedule that has not fired within that span never fires.
_SEARCH_DAYS = 146097 + 366


def _as_schedule(expr):
    if isinstance(expr, Schedule):
        return expr
    return parse(expr)


def _next_from(sched, after):
    if not isinstance(after, datetime):
        raise TypeError("after must be a datetime.datetime")
    if after.tzinfo is not None:
        raise ValueError("after must be a naive datetime")
    start = after.replace(second=0, microsecond=0)
    try:
        start += timedelta(minutes=1)
    except OverflowError:
        raise ValueError("no fire time representable after the given datetime")

    hours = sorted(sched.hours)
    minutes = sorted(sched.minutes)
    day = start.date()
    first_day = day
    for _ in range(_SEARCH_DAYS):
        weekday_sun0 = (day.weekday() + 1) % 7
        if sched.matches_day(day.year, day.month, day.day, weekday_sun0):
            for h in hours:
                if day == first_day and h < start.hour:
                    continue
                for m in minutes:
                    if day == first_day and h == start.hour and m < start.minute:
                        continue
                    return datetime(day.year, day.month, day.day, h, m)
        if day.month not in sched.months:
            # Jump straight to the first day of the next month.
            if day.month == 12:
                if day.year == 9999:
                    break
                day = date(day.year + 1, 1, 1)
            else:
                day = date(day.year, day.month + 1, 1)
            if (day - first_day).days > _SEARCH_DAYS:
                break
            continue
        if day == date.max:
            break
        day += timedelta(days=1)
    raise ValueError(f"schedule {sched.expr!r} never fires after {after.isoformat()}")


def next_fire(expr, after):
    """Return the first fire time strictly after ``after``."""
    return _next_from(_as_schedule(expr), after)


def next_fires(expr, after, n):
    """Return the next ``n`` fire times strictly after ``after``, in order."""
    if isinstance(n, bool) or not isinstance(n, int):
        raise TypeError("n must be an integer")
    if n < 0:
        raise ValueError("n must be non-negative")
    sched = _as_schedule(expr)
    result = []
    current = after
    for _ in range(n):
        current = _next_from(sched, current)
        result.append(current)
    return result
