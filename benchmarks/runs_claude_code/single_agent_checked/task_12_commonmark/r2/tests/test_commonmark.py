"""Unit tests for the CommonMark 0.31.2 renderer in ``src``.

The bulk of the tests are spec-style examples stored in
``examples_blocks.txt`` and ``examples_inlines.txt`` (same layout as the
CommonMark spec: markdown, a line with ".", expected HTML; "→" = tab).
"""

import ast
import io
import os
import subprocess
import sys
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.render import render  # noqa: E402
from src import cli  # noqa: E402
from src.blocks import parse  # noqa: E402
from src.inlines import normalize_reference, normalize_uri, unescape_string  # noqa: E402

FENCE = '`' * 32


def load_examples(filename):
    """Return a list of (section, number, markdown, html) tuples."""
    path = os.path.join(HERE, filename)
    with open(path, encoding='utf-8') as fh:
        lines = fh.read().split('\n')
    examples = []
    section = ''
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith('## '):
            section = line[3:].strip()
            i += 1
        elif line == FENCE + ' example':
            i += 1
            md_lines = []
            while lines[i] != '.':
                md_lines.append(lines[i])
                i += 1
            i += 1
            html_lines = []
            while lines[i] != FENCE:
                html_lines.append(lines[i])
                i += 1
            i += 1
            md = ''.join(l + '\n' for l in md_lines).replace('→', '\t')
            html = ''.join(l + '\n' for l in html_lines).replace('→', '\t')
            examples.append((section, len(examples) + 1, md, html))
        else:
            i += 1
    return examples


BLOCK_EXAMPLES = load_examples('examples_blocks.txt')
INLINE_EXAMPLES = load_examples('examples_inlines.txt')


class SpecExampleMixin:
    def check_section(self, examples, section):
        cases = [e for e in examples if e[0] == section]
        self.assertTrue(cases, 'no examples for section %r' % section)
        for sec, num, md, html in cases:
            with self.subTest(section=sec, example=num, markdown=md):
                self.assertEqual(render(md), html)


def _make_section_tests(cls, examples):
    sections = []
    for sec, _, _, _ in examples:
        if sec not in sections:
            sections.append(sec)
    for sec in sections:
        name = 'test_' + ''.join(c if c.isalnum() else '_' for c in sec.lower())

        def test(self, _sec=sec):
            self.check_section(examples, _sec)
        test.__name__ = name
        test.__doc__ = 'Spec examples: %s' % sec
        setattr(cls, name, test)
    return cls


class TestBlockSpecExamples(SpecExampleMixin, unittest.TestCase):
    """Container and leaf blocks (spec sections 2-5)."""


class TestInlineSpecExamples(SpecExampleMixin, unittest.TestCase):
    """Inline constructs (spec section 6)."""


_make_section_tests(TestBlockSpecExamples, BLOCK_EXAMPLES)
_make_section_tests(TestInlineSpecExamples, INLINE_EXAMPLES)


class TestExampleCorpus(unittest.TestCase):
    def test_corpus_size_and_coverage(self):
        self.assertGreaterEqual(len(BLOCK_EXAMPLES), 250)
        self.assertGreaterEqual(len(INLINE_EXAMPLES), 300)
        sections = {e[0] for e in BLOCK_EXAMPLES + INLINE_EXAMPLES}
        for required in [
                'Tabs', 'Thematic breaks', 'ATX headings', 'Setext headings',
                'Indented code blocks', 'Fenced code blocks', 'HTML blocks',
                'Link reference definitions', 'Paragraphs', 'Blank lines',
                'Block quotes', 'List items', 'Lists', 'Backslash escapes',
                'Entity and numeric character references', 'Code spans',
                'Emphasis and strong emphasis', 'Links', 'Images', 'Autolinks',
                'Raw HTML', 'Hard line breaks', 'Soft line breaks',
                'Textual content']:
            self.assertIn(required, sections)


class TestRenderApi(unittest.TestCase):
    def test_outcome_example(self):
        self.assertEqual(render('# Hi\n\n*a* **b**\n'),
                         '<h1>Hi</h1>\n<p><em>a</em> <strong>b</strong></p>\n')

    def test_heading_example_from_task(self):
        self.assertEqual(render('# Hi\n'), '<h1>Hi</h1>\n')

    def test_empty_input(self):
        self.assertEqual(render(''), '')
        self.assertEqual(render('\n\n\n'), '')

    def test_no_trailing_newline(self):
        self.assertEqual(render('foo'), '<p>foo</p>\n')

    def test_line_endings_crlf_and_cr(self):
        self.assertEqual(render('a\r\nb\r\n\r\nc\rd\r'), '<p>a\nb</p>\n<p>c\nd</p>\n')

    def test_nul_replaced(self):
        self.assertEqual(render('a\x00b\n'), '<p>a�b</p>\n')

    def test_entity_nul_replaced(self):
        self.assertEqual(render('&#0;&#x110000;&#xD800;\n'), '<p>���</p>\n')

    def test_returns_str(self):
        self.assertIsInstance(render('x'), str)

    def test_deeply_nested_blockquotes(self):
        md = '>' * 200 + ' a\n'
        html = render(md)
        self.assertEqual(html.count('<blockquote>'), 200)
        self.assertIn('<p>a</p>', html)

    def test_many_brackets_and_delimiters(self):
        md = '[' * 500 + 'a' + '*' * 500 + '\n'
        self.assertEqual(render(md), '<p>' + '[' * 500 + 'a' + '*' * 500 + '</p>\n')

    def test_many_unclosed_inline_links_is_fast(self):
        import time
        start = time.time()
        md = '[a](' * 10000 + '\n'
        self.assertEqual(render(md), '<p>' + '[a](' * 10000 + '</p>\n')
        self.assertLess(time.time() - start, 10)

    def test_balanced_parens_in_destination(self):
        self.assertEqual(render('[l](a(b(c)d)e)\n'),
                         '<p><a href="a(b(c)d)e">l</a></p>\n')

    def test_loose_list_with_trailing_blank_indented_code(self):
        md = '-     code\n\n- b\n'
        self.assertEqual(
            render(md),
            '<ul>\n<li>\n<pre><code>code\n</code></pre>\n</li>\n<li>\n<p>b</p>\n</li>\n</ul>\n')

    def test_html_block_type7_cannot_interrupt_paragraph(self):
        self.assertEqual(render('Foo\n<custom-tag>\nbar\n'),
                         '<p>Foo\n<custom-tag>\nbar</p>\n')

    def test_link_title_with_parentheses_and_escapes(self):
        self.assertEqual(render('[a](/u (t \\) x))\n'),
                         '<p><a href="/u" title="t ) x">a</a></p>\n')

    def test_image_title_escaping(self):
        self.assertEqual(render('![a "b"](/i.png "<t>")\n'),
                         '<p><img src="/i.png" alt="a &quot;b&quot;" title="&lt;t&gt;" /></p>\n')


class TestHelpers(unittest.TestCase):
    def test_normalize_reference(self):
        self.assertEqual(normalize_reference('[ Foo \n  BAR ]'), 'foo bar')
        self.assertEqual(normalize_reference('[ẞ]'), normalize_reference('[SS]'))

    def test_normalize_uri(self):
        self.assertEqual(normalize_uri('/a b'), '/a%20b')
        self.assertEqual(normalize_uri('%20%zz'), '%20%25zz')
        self.assertEqual(normalize_uri('ä'), '%C3%A4')
        self.assertEqual(normalize_uri("a;/?:@&=+$,-_.!~*'()#"), "a;/?:@&=+$,-_.!~*'()#")

    def test_unescape_string(self):
        self.assertEqual(unescape_string(r'\*a\b &amp; &ouml;'), '*a\\b & ö')

    def test_parse_tree_shape(self):
        doc = parse('- a\n- b\n')
        lst = doc.first_child
        self.assertEqual(lst.type, 'list')
        self.assertTrue(lst.list_data.tight)
        self.assertEqual([c.type for c in lst.children()], ['item', 'item'])


class TestCli(unittest.TestCase):
    def test_cli_calls_render(self):
        out = io.StringIO()
        with mock.patch.object(cli, 'render', wraps=cli.render) as spy:
            rc = cli.main(stdin=io.StringIO('*x*\n'), stdout=out)
        self.assertEqual(rc, 0)
        spy.assert_called_once_with('*x*\n')
        self.assertEqual(out.getvalue(), '<p><em>x</em></p>\n')

    def test_cli_source_references_render(self):
        with open(os.path.join(ROOT, 'src', 'cli.py'), encoding='utf-8') as fh:
            tree = ast.parse(fh.read())
        calls = [n for n in ast.walk(tree)
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                 and n.func.id == 'render']
        self.assertTrue(calls, 'src/cli.py must call render()')

    def test_cli_subprocess(self):
        md = '# Hi\n\n*a* **b** — ü\n'
        proc = subprocess.run(
            [sys.executable, '-m', 'src.cli'], input=md.encode('utf-8'),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=ROOT, timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode('utf-8', 'replace'))
        self.assertEqual(proc.stdout.decode('utf-8'),
                         '<h1>Hi</h1>\n<p><em>a</em> <strong>b</strong> — ü</p>\n')
        self.assertEqual(proc.stdout.decode('utf-8'), render(md))


if __name__ == '__main__':
    unittest.main()
