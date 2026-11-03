import io
import os
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from datetime import datetime
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src import cli  # noqa: E402
from src.parser import parse  # noqa: E402
from src.schedule import next_fire, next_fires  # noqa: E402

D = datetime


class TestParser(unittest.TestCase):
    def test_star_fields(self):
        s = parse("* * * * *")
        self.assertEqual(s.minutes, frozenset(range(60)))
        self.assertEqual(s.hours, frozenset(range(24)))
        self.assertEqual(s.days_of_month, frozenset(range(1, 32)))
        self.assertEqual(s.months, frozenset(range(1, 13)))
        self.assertEqual(s.days_of_week, frozenset(range(7)))
        self.assertTrue(s.dom_star and s.dow_star)

    def test_lists_ranges_steps(self):
        s = parse("1,5,10-12,20-40/10 */6 1-31/10 */5 1-5")
        self.assertEqual(s.minutes, {1, 5, 10, 11, 12, 20, 30, 40})
        self.assertEqual(s.hours, {0, 6, 12, 18})
        self.assertEqual(s.days_of_month, {1, 11, 21, 31})
        self.assertEqual(s.months, {1, 6, 11})
        self.assertEqual(s.days_of_week, {1, 2, 3, 4, 5})

    def test_step_larger_than_range(self):
        self.assertEqual(parse("*/100 * * * *").minutes, {0})
        self.assertEqual(parse("5-10/30 * * * *").minutes, {5})

    def test_leading_zeros(self):
        self.assertEqual(parse("05 007 * * *").minutes, {5})

    def test_dow_seven_is_sunday(self):
        self.assertEqual(parse("0 0 * * 7").days_of_week, {0})
        self.assertEqual(parse("0 0 * * 5-7").days_of_week, {5, 6, 0})
        self.assertEqual(parse("0 0 * * */2").days_of_week, {0, 2, 4, 6})
        self.assertEqual(parse("0 0 * * 1-7").days_of_week, set(range(7)))

    def test_names_case_insensitive_in_lists_and_ranges(self):
        s = parse("0 0 * JAN,mar,Dec mon-FRI")
        self.assertEqual(s.months, {1, 3, 12})
        self.assertEqual(s.days_of_week, {1, 2, 3, 4, 5})
        self.assertEqual(parse("0 0 * jan-dec/3 sun").months, {1, 4, 7, 10})
        self.assertEqual(parse("0 0 * * sat,sun").days_of_week, {0, 6})
        self.assertEqual(parse("0 0 * 2-apr 1-wed").months, {2, 3, 4})

    def test_star_flags(self):
        self.assertFalse(parse("0 0 1 * 1").dom_star)
        self.assertFalse(parse("0 0 1 * 1").dow_star)
        self.assertTrue(parse("0 0 */2 * 1").dom_star)
        self.assertTrue(parse("0 0 1 * */2").dow_star)

    def test_whitespace(self):
        self.assertEqual(parse("  0\t12  *   * *  ").hours, {12})

    def test_shortcuts(self):
        cases = {
            "@yearly": "0 0 1 1 *",
            "@annually": "0 0 1 1 *",
            "@monthly": "0 0 1 * *",
            "@weekly": "0 0 * * 0",
            "@daily": "0 0 * * *",
            "@midnight": "0 0 * * *",
            "@hourly": "0 * * * *",
        }
        for short, full in cases.items():
            with self.subTest(short=short):
                a, b = parse(short), parse(full)
                for attr in ("minutes", "hours", "days_of_month", "months",
                             "days_of_week", "dom_star", "dow_star"):
                    self.assertEqual(getattr(a, attr), getattr(b, attr))

    def test_invalid_expressions(self):
        bad = [
            "", "   ", "* * * *", "* * * * * *", "@reboot", "@foo", "@",
            "@YEARLY", "@daily *",
            "60 * * * *", "* 24 * * *", "* * 0 * *", "* * 32 * *",
            "* * * 0 *", "* * * 13 *", "* * * * 8", "-1 * * * *",
            "*/0 * * * *", "1-5/0 * * * *", "*/ * * * *", "*/-1 * * * *",
            "5/10 * * * *", "mon/2 * * * *", "* * * * mon/2",
            "5-1 * * * *", "* * * dec-jan *", "1,,2 * * * *", "1, * * * *",
            ",1 * * * *", "1- * * * *", "-5 * * * *", "1-2-3 * * * *",
            "*-5 * * * *", "** * * * *", "*5 * * * *", "*/5/2 * * * *",
            "a * * * *", "jan * * * *", "* mon * * *", "* * * mon *",
            "* * * jan,feb jan", "* * * * monday", "* * * january *",
            "* * * * 1.5", "1.0 * * * *", "+5 * * * *", "? * * * *",
            "* * L * *", "* * * * 5#2", "* * 15W * *", "١ * * * *",
            "0 0 1 1 * 2027",
        ]
        for expr in bad:
            with self.subTest(expr=expr):
                with self.assertRaises(ValueError):
                    parse(expr)
                with self.assertRaises(ValueError):
                    next_fire(expr, D(2026, 1, 1))

    def test_non_string(self):
        with self.assertRaises(ValueError):
            parse(None)


class TestNextFire(unittest.TestCase):
    def test_outcome_example(self):
        # 2026-11-06 is a Friday; the next weekday 09:00 is Monday the 9th.
        self.assertEqual(D(2026, 11, 6).weekday(), 4)
        self.assertEqual(next_fire("0 9 * * 1-5", D(2026, 11, 6, 10, 0)),
                         D(2026, 11, 9, 9, 0))

    def test_strictly_after(self):
        self.assertEqual(next_fire("* * * * *", D(2026, 1, 1, 0, 0)),
                         D(2026, 1, 1, 0, 1))
        self.assertEqual(next_fire("0 9 * * *", D(2026, 1, 1, 9, 0)),
                         D(2026, 1, 2, 9, 0))
        self.assertEqual(next_fire("0 9 * * *", D(2026, 1, 1, 8, 59, 59, 999999)),
                         D(2026, 1, 1, 9, 0))

    def test_seconds_truncated(self):
        r = next_fire("* * * * *", D(2026, 1, 1, 0, 0, 30, 123))
        self.assertEqual(r, D(2026, 1, 1, 0, 1))
        self.assertEqual((r.second, r.microsecond), (0, 0))

    def test_every_15_minutes(self):
        self.assertEqual(next_fires("*/15 * * * *", D(2026, 3, 1, 10, 7), 4),
                         [D(2026, 3, 1, 10, 15), D(2026, 3, 1, 10, 30),
                          D(2026, 3, 1, 10, 45), D(2026, 3, 1, 11, 0)])

    def test_rollovers(self):
        self.assertEqual(next_fire("59 23 * * *", D(2026, 12, 31, 23, 59)),
                         D(2027, 1, 1, 23, 59))
        self.assertEqual(next_fire("0 0 1 * *", D(2026, 1, 31, 12, 0)),
                         D(2026, 2, 1, 0, 0))
        self.assertEqual(next_fire("0 0 1 1 *", D(2026, 6, 1)), D(2027, 1, 1))
        self.assertEqual(next_fire("30 23 31 12 *", D(2026, 12, 31, 23, 30)),
                         D(2027, 12, 31, 23, 30))

    def test_hours_and_minutes_lists(self):
        self.assertEqual(
            next_fires("0,30 8-9 * * *", D(2026, 5, 5, 8, 15), 4),
            [D(2026, 5, 5, 8, 30), D(2026, 5, 5, 9, 0), D(2026, 5, 5, 9, 30),
             D(2026, 5, 6, 8, 0)])

    def test_day_31_skips_short_months(self):
        self.assertEqual(next_fires("0 0 31 * *", D(2026, 1, 31), 3),
                         [D(2026, 3, 31), D(2026, 5, 31), D(2026, 7, 31)])

    def test_leap_day(self):
        self.assertEqual(next_fire("0 0 29 2 *", D(2026, 1, 1)), D(2028, 2, 29))
        # 2100 is not a leap year.
        self.assertEqual(next_fire("0 0 29 2 *", D(2096, 3, 1)), D(2104, 2, 29))

    def test_dom_dow_or_when_both_restricted(self):
        # 2026-11-01 is a Sunday; Fridays are 6, 13, 20.
        self.assertEqual(D(2026, 11, 1).weekday(), 6)
        self.assertEqual(next_fires("0 0 13 * 5", D(2026, 11, 1), 3),
                         [D(2026, 11, 6), D(2026, 11, 13), D(2026, 11, 20)])
        self.assertEqual(
            next_fires("0 0 1 * mon", D(2026, 11, 28), 4),
            [D(2026, 11, 30), D(2026, 12, 1), D(2026, 12, 7), D(2026, 12, 14)])

    def test_dom_dow_and_when_field_starts_with_star(self):
        # dom "*/2" starts with '*', so both fields must match:
        # odd days of the month that are Mondays.
        self.assertEqual(
            next_fires("0 0 */2 * 1", D(2026, 11, 1), 4),
            [D(2026, 11, 9), D(2026, 11, 23), D(2026, 12, 7), D(2026, 12, 21)])
        # dow "*/3" -> {0, 3, 6}; with dom 1-7 both must match.
        self.assertEqual(
            next_fires("0 0 1-7 * */3", D(2026, 11, 1), 3),
            [D(2026, 11, 4), D(2026, 11, 7), D(2026, 12, 2)])

    def test_dow_only(self):
        self.assertEqual(next_fires("0 12 * * sun", D(2026, 11, 1, 12, 0), 2),
                         [D(2026, 11, 8, 12), D(2026, 11, 15, 12)])
        self.assertEqual(next_fire("0 12 * * 7", D(2026, 11, 1, 12, 0)),
                         D(2026, 11, 8, 12))
        self.assertEqual(next_fires("0 0 * * 5-7", D(2026, 11, 5), 4),
                         [D(2026, 11, 6), D(2026, 11, 7), D(2026, 11, 8),
                          D(2026, 11, 13)])

    def test_month_names(self):
        self.assertEqual(next_fires("0 0 1 jan,jul *", D(2026, 2, 1), 2),
                         [D(2026, 7, 1), D(2027, 1, 1)])

    def test_shortcut_fires(self):
        after = D(2026, 11, 6, 10, 0)  # Friday
        self.assertEqual(next_fire("@yearly", after), D(2027, 1, 1))
        self.assertEqual(next_fire("@annually", after), D(2027, 1, 1))
        self.assertEqual(next_fire("@monthly", after), D(2026, 12, 1))
        self.assertEqual(next_fire("@weekly", after), D(2026, 11, 8))
        self.assertEqual(next_fire("@daily", after), D(2026, 11, 7))
        self.assertEqual(next_fire("@midnight", after), D(2026, 11, 7))
        self.assertEqual(next_fire("@hourly", after), D(2026, 11, 6, 11, 0))

    def test_never_fires_raises(self):
        for expr in ("0 0 30 2 *", "0 0 31 4,6,9,11 *", "0 0 31 2 *"):
            with self.subTest(expr=expr):
                with self.assertRaises(ValueError):
                    next_fire(expr, D(2026, 1, 1))

    def test_rare_but_possible(self):
        # dom 29, month 2, dow '*' -> only leap days.
        r = next_fire("0 0 29 2 *", D(2028, 2, 29))
        self.assertEqual(r, D(2032, 2, 29))

    def test_end_of_range(self):
        with self.assertRaises(ValueError):
            next_fire("* * * * *", D(9999, 12, 31, 23, 59))

    def test_next_fires_counts(self):
        self.assertEqual(next_fires("* * * * *", D(2026, 1, 1), 0), [])
        with self.assertRaises(ValueError):
            next_fires("* * * * *", D(2026, 1, 1), -1)
        res = next_fires("0 0 * * *", D(2026, 1, 1), 10)
        self.assertEqual(len(res), 10)
        self.assertEqual(res, sorted(res))
        self.assertEqual(len(set(res)), 10)
        for r in res:
            self.assertEqual((r.second, r.microsecond), (0, 0))

    def test_accepts_schedule_object(self):
        self.assertEqual(next_fire(parse("0 9 * * 1-5"), D(2026, 11, 6, 10)),
                         D(2026, 11, 9, 9))


class TestCli(unittest.TestCase):
    def test_cli_calls_next_fires(self):
        with mock.patch.object(cli, "next_fires", wraps=cli.next_fires) as m:
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = cli.main(["0 9 * * 1-5", "2026-11-06T10:00", "2"])
        self.assertEqual(rc, 0)
        m.assert_called_once_with("0 9 * * 1-5", D(2026, 11, 6, 10, 0), 2)
        self.assertEqual(buf.getvalue().splitlines(),
                         ["2026-11-09T09:00:00", "2026-11-10T09:00:00"])

    def test_cli_subprocess(self):
        out = subprocess.run(
            [sys.executable, "-m", "src.cli", "*/30 * * * *", "2026-01-01T00:00:00", "3"],
            cwd=ROOT, capture_output=True, text=True, check=True).stdout
        self.assertEqual(out.splitlines(), ["2026-01-01T00:30:00",
                                            "2026-01-01T01:00:00",
                                            "2026-01-01T01:30:00"])
        out = subprocess.run(
            [sys.executable, "-m", "src.cli", "@daily", "2026-01-01T05:00:00"],
            cwd=ROOT, capture_output=True, text=True, check=True).stdout
        self.assertEqual(out.splitlines(), ["2026-01-02T00:00:00"])

    def test_cli_invalid(self):
        buf = io.StringIO()
        with mock.patch("sys.stderr", buf):
            self.assertNotEqual(cli.main(["61 * * * *", "2026-01-01T00:00"]), 0)
            self.assertNotEqual(cli.main(["* * * * *"]), 0)


if __name__ == "__main__":
    unittest.main()
