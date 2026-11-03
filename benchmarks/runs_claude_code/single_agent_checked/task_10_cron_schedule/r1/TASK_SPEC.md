# Build Task 10: Cron Schedule Calculator

Implement a cron expression parser and next-fire calculator under `src/` that follows standard cron semantics as documented in crontab(5) for Vixie cron / cronie, with unit tests under `tests/test_cron.py`.

## Required Files & API Specification
1. Expressions have the five standard time fields (minute, hour, day of month, month, day of week) with all the syntax crontab(5) defines for them, plus the `@yearly`, `@annually`, `@monthly`, `@weekly`, `@daily`, `@midnight` and `@hourly` shortcuts (`@reboot` is not supported).
2. `src/parser.py`: `parse(expr: str) -> Schedule`; raises `ValueError` for any expression crontab(5) does not accept.
3. `src/schedule.py`:
   - `next_fire(expr: str, after: datetime) -> datetime`: the first time strictly after `after` at which the schedule fires. Datetimes are naive (no time zones); results have `second == 0` and `microsecond == 0`.
   - `next_fires(expr: str, after: datetime, n: int) -> list[datetime]`: the next `n` fire times after `after`, in order.
4. `src/cli.py`: CLI entrypoint `python3 -m src.cli "<expr>" <iso-datetime> [n]` printing one ISO datetime per line.
5. `tests/test_cron.py`: unit test suite runnable via `python3 -m unittest discover -s tests -v`.

## Rules
- Python standard library only: no third-party packages.
- Work from your knowledge of the referenced standard. Do not run, import, or consult another implementation of it (for example Node's `semver`, the `git` binary, `croniter`, or any package) — neither at runtime nor to produce expected values for your tests.

## Acceptance Criteria & Self-Checks
Before reporting the task done, make sure each of these holds and is covered by an automated test:
1. Every expression is interpreted exactly as crontab(5) (Vixie cron / cronie) defines, and anything it rejects raises ValueError
2. src/cli.py must call next_fires

- Verification command (must exit 0): `python3 -m unittest discover -s tests -v`
- Outcome command (stdout must contain `CRON_OK`): `python3 -c "from datetime import datetime; from src.schedule import next_fire; assert next_fire('0 9 * * 1-5', datetime(2026, 11, 6, 10, 0)) == datetime(2026, 11, 9, 9, 0); print('CRON_OK')"`
