# Build Task 9: npm-Compatible Semantic Version Ranges

Implement Python modules under `src/` that reproduce the behaviour of the npm `semver` package (node-semver 7.x) with its default options (not loose, `includePrerelease` off), with unit tests under `tests/test_semver.py`.

## Required Files & API Specification
1. `src/version.py`:
   - `valid(text: str) -> str | None`: like `semver.valid(text)`: the normalized version string, or `None` if `text` is not a valid version.
   - `compare(a: str, b: str) -> int`: like `semver.compare(a, b)`: `-1`, `0` or `1` by version precedence. Raises `ValueError` for an invalid version.
2. `src/ranges.py`:
   - `satisfies(version: str, range_text: str) -> bool`: like `semver.satisfies(version, range_text)`, including returning `False` for an invalid version or range.
   - `max_satisfying(versions: list[str], range_text: str) -> str | None`: like `semver.maxSatisfying`: the highest version in `versions` that satisfies the range, returned exactly as given, or `None`.
   - Support every range syntax node-semver accepts in default mode.
3. `src/cli.py`: CLI entrypoint `python3 -m src.cli satisfies <version> <range>` (prints `true`/`false`) and `python3 -m src.cli max <range> <version>...` (prints the result or `null`).
4. `tests/test_semver.py`: unit test suite runnable via `python3 -m unittest discover -s tests -v`.

## Rules
- Python standard library only: no third-party packages.
- Work from your knowledge of the referenced standard. Do not run, import, or consult another implementation of it (for example Node's `semver`, the `git` binary, `croniter`, or any package) — neither at runtime nor to produce expected values for your tests.

## Acceptance Criteria & Self-Checks
Before reporting the task done, make sure each of these holds and is covered by an automated test:
1. Every function behaves like node-semver 7.x with default options, for all inputs node-semver accepts or rejects
2. src/cli.py must call satisfies and max_satisfying

- Verification command (must exit 0): `python3 -m unittest discover -s tests -v`
- Outcome command (stdout must contain `SEMVER_OK`): `python3 -c "from src.ranges import satisfies, max_satisfying; assert satisfies('1.2.5', '^1.2.3') and not satisfies('2.0.0', '^1.2.3'); assert max_satisfying(['1.2.3', '1.4.0', '2.0.0'], '~1.2') == '1.2.3'; print('SEMVER_OK')"`
