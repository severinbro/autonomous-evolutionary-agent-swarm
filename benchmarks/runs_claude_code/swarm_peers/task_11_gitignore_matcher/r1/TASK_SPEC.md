# Build Task 11: Gitignore Matcher

Implement under `src/` a matcher that decides which files Git ignores, given the contents of a single top-level `.gitignore`, exactly as Git does for untracked files (gitignore(5)), with unit tests under `tests/test_gitignore.py`.

## Required Files & API Specification
1. `src/patterns.py`: parsing of `.gitignore` lines into patterns.
2. `src/matcher.py`:
   - `GitIgnore(text: str)`: built from the full text of the `.gitignore` file.
   - `is_ignored(path: str) -> bool`: whether Git ignores the file at `path`, a path relative to the repository root with `/` separators. Paths always name files, never directories.
   - `ignored_files(paths: list[str]) -> list[str]`: the ignored paths, sorted.
3. `src/cli.py`: CLI entrypoint `python3 -m src.cli <gitignore_path> <path>...` printing each ignored path on its own line.
4. Scope: only the one `.gitignore` at the repository root applies (no nested `.gitignore` files, no `.git/info/exclude`, no global excludes file). Paths are case-sensitive.
5. `tests/test_gitignore.py`: unit test suite runnable via `python3 -m unittest discover -s tests -v`.

## Rules
- Python standard library only: no third-party packages.
- Work from your knowledge of the referenced standard. Do not run, import, or consult another implementation of it (for example Node's `semver`, the `git` binary, `croniter`, or any package) — neither at runtime nor to produce expected values for your tests.

## Acceptance Criteria & Self-Checks
Before reporting the task done, make sure each of these holds and is covered by an automated test:
1. is_ignored matches what Git itself reports for untracked files under the given .gitignore, for every pattern form gitignore(5) documents
2. src/cli.py must call GitIgnore

- Verification command (must exit 0): `python3 -m unittest discover -s tests -v`
- Outcome command (stdout must contain `GITIGNORE_OK`): `python3 -c "from src.matcher import GitIgnore; g = GitIgnore('*.log\n'); assert g.is_ignored('a/b.log') and not g.is_ignored('a/b.txt'); print('GITIGNORE_OK')"`
