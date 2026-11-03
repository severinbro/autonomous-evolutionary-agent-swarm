# Build Task 12: CommonMark Markdown Renderer

Implement a Markdown-to-HTML renderer under `src/` that conforms to the CommonMark Spec, version 0.31.2, with unit tests under `tests/test_commonmark.py`.

## Required Files & API Specification
1. `src/blocks.py`: block-structure parsing (container and leaf blocks, link reference definitions).
2. `src/inlines.py`: inline parsing (code spans, emphasis and strong emphasis, links and images, autolinks, raw HTML, hard and soft line breaks, backslash escapes, entity and numeric character references).
3. `src/render.py`: `render(markdown: str) -> str` returning the HTML the CommonMark reference implementation produces for `markdown`, in the same form as the spec's examples (for example `"# Hi\n"` renders as `"<h1>Hi</h1>\n"`).
4. `src/cli.py`: CLI entrypoint `python3 -m src.cli` that reads Markdown from stdin and writes HTML to stdout.
5. `tests/test_commonmark.py`: unit test suite runnable via `python3 -m unittest discover -s tests -v`.

## Rules
- Python standard library only: no third-party packages.
- Work from your knowledge of the referenced standard. Do not run, import, or consult another implementation of it (for example Node's `semver`, the `git` binary, `croniter`, or any package) — neither at runtime nor to produce expected values for your tests.
- No network access: do not download the spec, its examples, or any other material.

## Acceptance Criteria & Self-Checks
Before reporting the task done, make sure each of these holds and is covered by an automated test:
1. render() output matches the CommonMark 0.31.2 reference implementation for every construct the spec defines
2. src/cli.py must call render

- Verification command (must exit 0): `python3 -m unittest discover -s tests -v`
- Outcome command (stdout must contain `COMMONMARK_OK`): `python3 -c "from src.render import render; assert render('# Hi\\n\\n*a* **b**\\n') == '<h1>Hi</h1>\\n<p><em>a</em> <strong>b</strong></p>\\n'; print('COMMONMARK_OK')"`
