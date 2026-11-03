"""Tests for the CommonMark 0.31.2 renderer.

Expected outputs are taken from the examples of the CommonMark spec, written
out from knowledge of the specification, grouped by spec section.
"""

import io
import os
import subprocess
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.render import render  # noqa: E402
from src import cli  # noqa: E402
from src import blocks, inlines  # noqa: E402


class SpecCase(unittest.TestCase):
    CASES = []

    def check_cases(self):
        for i, (md, html) in enumerate(self.CASES):
            with self.subTest(i=i, markdown=md):
                self.assertEqual(render(md), html)


class TestTabs(SpecCase):
    CASES = [
        ("\tfoo\tbaz\t\tbim\n", "<pre><code>foo\tbaz\t\tbim\n</code></pre>\n"),
        ("  \tfoo\tbaz\t\tbim\n", "<pre><code>foo\tbaz\t\tbim\n</code></pre>\n"),
        ("    a\ta\n    \u1f50\ta\n", "<pre><code>a\ta\n\u1f50\ta\n</code></pre>\n"),
        ("  - foo\n\n\tbar\n", "<ul>\n<li>\n<p>foo</p>\n<p>bar</p>\n</li>\n</ul>\n"),
        ("- foo\n\n\t\tbar\n",
         "<ul>\n<li>\n<p>foo</p>\n<pre><code>  bar\n</code></pre>\n</li>\n</ul>\n"),
        (">\t\tfoo\n", "<blockquote>\n<pre><code>  foo\n</code></pre>\n</blockquote>\n"),
        ("-\t\tfoo\n", "<ul>\n<li>\n<pre><code>  foo\n</code></pre>\n</li>\n</ul>\n"),
        ("    foo\n\tbar\n", "<pre><code>foo\nbar\n</code></pre>\n"),
        (" - foo\n   - bar\n\t - baz\n",
         "<ul>\n<li>foo\n<ul>\n<li>bar\n<ul>\n<li>baz</li>\n</ul>\n</li>\n</ul>\n</li>\n</ul>\n"),
        ("#\tFoo\n", "<h1>Foo</h1>\n"),
        ("*\t*\t*\t\n", "<hr />\n"),
    ]

    def test_tabs(self):
        self.check_cases()


class TestBackslashEscapes(SpecCase):
    CASES = [
        ("\\!\\\"\\#\\$\\%\\&\\'\\(\\)\\*\\+\\,\\-\\.\\/\\:\\;\\<\\=\\>\\?\\@\\[\\\\\\]\\^\\_\\`\\{\\|\\}\\~\n",
         "<p>!&quot;#$%&amp;'()*+,-./:;&lt;=&gt;?@[\\]^_`{|}~</p>\n"),
        ("\\\t\\A\\a\\ \\3\\\u03c6\\\u00ab\n", "<p>\\\t\\A\\a\\ \\3\\\u03c6\\\u00ab</p>\n"),
        ("\\*not emphasized*\n\\<br/> not a tag\n\\[not a link](/foo)\n\\`not code`\n"
         "1\\. not a list\n\\* not a list\n\\# not a heading\n"
         "\\[foo]: /url \"not a reference\"\n\\&ouml; not a character entity\n",
         "<p>*not emphasized*\n&lt;br/&gt; not a tag\n[not a link](/foo)\n`not code`\n"
         "1. not a list\n* not a list\n# not a heading\n"
         "[foo]: /url &quot;not a reference&quot;\n&amp;ouml; not a character entity</p>\n"),
        ("\\\\*emphasis*\n", "<p>\\<em>emphasis</em></p>\n"),
        ("foo\\\nbar\n", "<p>foo<br />\nbar</p>\n"),
        ("`` \\[\\` ``\n", "<p><code>\\[\\`</code></p>\n"),
        ("    \\[\\]\n", "<pre><code>\\[\\]\n</code></pre>\n"),
        ("~~~\n\\[\\]\n~~~\n", "<pre><code>\\[\\]\n</code></pre>\n"),
        ("<https://example.com?find=\\*>\n",
         "<p><a href=\"https://example.com?find=%5C*\">https://example.com?find=\\*</a></p>\n"),
        ("<a href=\"/bar\\/)\">\n", "<a href=\"/bar\\/)\">\n"),
        ("[foo](/bar\\* \"ti\\*tle\")\n", "<p><a href=\"/bar*\" title=\"ti*tle\">foo</a></p>\n"),
        ("[foo]\n\n[foo]: /bar\\* \"ti\\*tle\"\n",
         "<p><a href=\"/bar*\" title=\"ti*tle\">foo</a></p>\n"),
        ("``` foo\\+bar\nfoo\n```\n",
         "<pre><code class=\"language-foo+bar\">foo\n</code></pre>\n"),
    ]

    def test_backslash_escapes(self):
        self.check_cases()


class TestEntities(SpecCase):
    CASES = [
        ("&nbsp; &amp; &copy; &AElig; &Dcaron;\n&frac34; &HilbertSpace; &DifferentialD;\n"
         "&ClockwiseContourIntegral; &ngE;\n",
         "<p>\u00a0 &amp; \u00a9 \u00c6 \u010e\n\u00be \u210b \u2146\n\u2232 \u2267\u0338</p>\n"),
        ("&#35; &#1234; &#992; &#0;\n", "<p># \u04d2 \u03e0 \ufffd</p>\n"),
        ("&#X22; &#XD06; &#xcab;\n", "<p>&quot; \u0d06 \u0cab</p>\n"),
        ("&nbsp &x; &#; &#x;\n&#87654321;\n&#abcdef0;\n&ThisIsNotDefined; &hi?;\n",
         "<p>&amp;nbsp &amp;x; &amp;#; &amp;#x;\n&amp;#87654321;\n&amp;#abcdef0;\n"
         "&amp;ThisIsNotDefined; &amp;hi?;</p>\n"),
        ("&copy\n", "<p>&amp;copy</p>\n"),
        ("&MadeUpEntity;\n", "<p>&amp;MadeUpEntity;</p>\n"),
        ("<a href=\"&ouml;&ouml;.html\">\n", "<a href=\"&ouml;&ouml;.html\">\n"),
        ("[foo](/f&ouml;&ouml; \"f&ouml;&ouml;\")\n",
         "<p><a href=\"/f%C3%B6%C3%B6\" title=\"f\u00f6\u00f6\">foo</a></p>\n"),
        ("[foo]\n\n[foo]: /f&ouml;&ouml; \"f&ouml;&ouml;\"\n",
         "<p><a href=\"/f%C3%B6%C3%B6\" title=\"f\u00f6\u00f6\">foo</a></p>\n"),
        ("``` f&ouml;&ouml;\nfoo\n```\n",
         "<pre><code class=\"language-f\u00f6\u00f6\">foo\n</code></pre>\n"),
        ("`f&ouml;&ouml;`\n", "<p><code>f&amp;ouml;&amp;ouml;</code></p>\n"),
        ("    f&ouml;f&ouml;\n", "<pre><code>f&amp;ouml;f&amp;ouml;\n</code></pre>\n"),
        ("&#42;foo&#42;\n*foo*\n", "<p>*foo*\n<em>foo</em></p>\n"),
        ("&#42; foo\n\n* foo\n", "<p>* foo</p>\n<ul>\n<li>foo</li>\n</ul>\n"),
        ("foo&#10;&#10;bar\n", "<p>foo\n\nbar</p>\n"),
        ("&#9;foo\n", "<p>\tfoo</p>\n"),
        ("[a](url &quot;tit&quot;)\n", "<p>[a](url &quot;tit&quot;)</p>\n"),
    ]

    def test_entities(self):
        self.check_cases()


class TestPrecedence(SpecCase):
    CASES = [
        ("- `one\n- two`\n", "<ul>\n<li>`one</li>\n<li>two`</li>\n</ul>\n"),
    ]

    def test_precedence(self):
        self.check_cases()


class TestThematicBreaks(SpecCase):
    CASES = [
        ("***\n---\n___\n", "<hr />\n<hr />\n<hr />\n"),
        ("+++\n", "<p>+++</p>\n"),
        ("===\n", "<p>===</p>\n"),
        ("--\n**\n__\n", "<p>--\n**\n__</p>\n"),
        (" ***\n  ***\n   ***\n", "<hr />\n<hr />\n<hr />\n"),
        ("    ***\n", "<pre><code>***\n</code></pre>\n"),
        ("Foo\n    ***\n", "<p>Foo\n***</p>\n"),
        ("_____________________________________\n", "<hr />\n"),
        (" - - -\n", "<hr />\n"),
        (" **  * ** * ** * **\n", "<hr />\n"),
        ("-     -      -      -\n", "<hr />\n"),
        ("- - - -    \n", "<hr />\n"),
        ("_ _ _ _ a\n\na------\n\n---a---\n",
         "<p>_ _ _ _ a</p>\n<p>a------</p>\n<p>---a---</p>\n"),
        (" *-*\n", "<p><em>-</em></p>\n"),
        ("- foo\n***\n- bar\n", "<ul>\n<li>foo</li>\n</ul>\n<hr />\n<ul>\n<li>bar</li>\n</ul>\n"),
        ("Foo\n***\nbar\n", "<p>Foo</p>\n<hr />\n<p>bar</p>\n"),
        ("Foo\n---\nbar\n", "<h2>Foo</h2>\n<p>bar</p>\n"),
        ("* Foo\n* * *\n* Bar\n", "<ul>\n<li>Foo</li>\n</ul>\n<hr />\n<ul>\n<li>Bar</li>\n</ul>\n"),
        ("- Foo\n- * * *\n", "<ul>\n<li>Foo</li>\n<li>\n<hr />\n</li>\n</ul>\n"),
    ]

    def test_thematic_breaks(self):
        self.check_cases()


class TestATXHeadings(SpecCase):
    CASES = [
        ("# foo\n## foo\n### foo\n#### foo\n##### foo\n###### foo\n",
         "<h1>foo</h1>\n<h2>foo</h2>\n<h3>foo</h3>\n<h4>foo</h4>\n<h5>foo</h5>\n<h6>foo</h6>\n"),
        ("####### foo\n", "<p>####### foo</p>\n"),
        ("#5 bolt\n\n#hashtag\n", "<p>#5 bolt</p>\n<p>#hashtag</p>\n"),
        ("\\## foo\n", "<p>## foo</p>\n"),
        ("# foo *bar* \\*baz\\*\n", "<h1>foo <em>bar</em> *baz*</h1>\n"),
        ("#                  foo                     \n", "<h1>foo</h1>\n"),
        (" ### foo\n  ## foo\n   # foo\n", "<h3>foo</h3>\n<h2>foo</h2>\n<h1>foo</h1>\n"),
        ("    # foo\n", "<pre><code># foo\n</code></pre>\n"),
        ("foo\n    # bar\n", "<p>foo\n# bar</p>\n"),
        ("## foo ##\n  ###   bar    ###\n", "<h2>foo</h2>\n<h3>bar</h3>\n"),
        ("# foo ##################################\n##### foo ##\n",
         "<h1>foo</h1>\n<h5>foo</h5>\n"),
        ("### foo ###     \n", "<h3>foo</h3>\n"),
        ("### foo ### b\n", "<h3>foo ### b</h3>\n"),
        ("# foo#\n", "<h1>foo#</h1>\n"),
        ("### foo \\###\n## foo #\\##\n# foo \\#\n",
         "<h3>foo ###</h3>\n<h2>foo ###</h2>\n<h1>foo #</h1>\n"),
        ("****\n## foo\n****\n", "<hr />\n<h2>foo</h2>\n<hr />\n"),
        ("Foo bar\n# baz\nBar foo\n", "<p>Foo bar</p>\n<h1>baz</h1>\n<p>Bar foo</p>\n"),
        ("## \n#\n### ###\n", "<h2></h2>\n<h1></h1>\n<h3></h3>\n"),
    ]

    def test_atx_headings(self):
        self.check_cases()


class TestSetextHeadings(SpecCase):
    CASES = [
        ("Foo *bar*\n=========\n\nFoo *bar*\n---------\n",
         "<h1>Foo <em>bar</em></h1>\n<h2>Foo <em>bar</em></h2>\n"),
        ("Foo *bar\nbaz*\n====\n", "<h1>Foo <em>bar\nbaz</em></h1>\n"),
        ("  Foo *bar\nbaz*\t\n====\n", "<h1>Foo <em>bar\nbaz</em></h1>\n"),
        ("Foo\n-------------------------\n\nFoo\n=\n", "<h2>Foo</h2>\n<h1>Foo</h1>\n"),
        ("   Foo\n---\n\n  Foo\n-----\n\n  Foo\n  ===\n",
         "<h2>Foo</h2>\n<h2>Foo</h2>\n<h1>Foo</h1>\n"),
        ("    Foo\n    ---\n\n    Foo\n---\n",
         "<pre><code>Foo\n---\n\nFoo\n</code></pre>\n<hr />\n"),
        ("Foo\n   ----      \n", "<h2>Foo</h2>\n"),
        ("Foo\n    ---\n", "<p>Foo\n---</p>\n"),
        ("Foo\n= =\n\nFoo\n--- -\n", "<p>Foo\n= =</p>\n<p>Foo</p>\n<hr />\n"),
        ("Foo  \n-----\n", "<h2>Foo</h2>\n"),
        ("Foo\\\n----\n", "<h2>Foo\\</h2>\n"),
        ("`Foo\n----\n`\n\n<a title=\"a lot\n---\nof dashes\"/>\n",
         "<h2>`Foo</h2>\n<p>`</p>\n<h2>&lt;a title=&quot;a lot</h2>\n<p>of dashes&quot;/&gt;</p>\n"),
        ("> Foo\n---\n", "<blockquote>\n<p>Foo</p>\n</blockquote>\n<hr />\n"),
        ("> foo\nbar\n===\n", "<blockquote>\n<p>foo\nbar\n===</p>\n</blockquote>\n"),
        ("- Foo\n---\n", "<ul>\n<li>Foo</li>\n</ul>\n<hr />\n"),
        ("Foo\nBar\n---\n", "<h2>Foo\nBar</h2>\n"),
        ("---\nFoo\n---\nBar\n---\nBaz\n", "<hr />\n<h2>Foo</h2>\n<h2>Bar</h2>\n<p>Baz</p>\n"),
        ("\n====\n", "<p>====</p>\n"),
        ("---\n---\n", "<hr />\n<hr />\n"),
        ("- foo\n-----\n", "<ul>\n<li>foo</li>\n</ul>\n<hr />\n"),
        ("    foo\n---\n", "<pre><code>foo\n</code></pre>\n<hr />\n"),
        ("> foo\n-----\n", "<blockquote>\n<p>foo</p>\n</blockquote>\n<hr />\n"),
        ("\\> foo\n------\n", "<h2>&gt; foo</h2>\n"),
        ("Foo\n\nbar\n---\nbaz\n", "<p>Foo</p>\n<h2>bar</h2>\n<p>baz</p>\n"),
        ("Foo\nbar\n\n---\n\nbaz\n", "<p>Foo\nbar</p>\n<hr />\n<p>baz</p>\n"),
        ("Foo\nbar\n* * *\nbaz\n", "<p>Foo\nbar</p>\n<hr />\n<p>baz</p>\n"),
        ("Foo\nbar\n\\---\nbaz\n", "<p>Foo\nbar\n---\nbaz</p>\n"),
    ]

    def test_setext_headings(self):
        self.check_cases()


class TestIndentedCode(SpecCase):
    CASES = [
        ("    a simple\n      indented code block\n",
         "<pre><code>a simple\n  indented code block\n</code></pre>\n"),
        ("  - foo\n\n    bar\n", "<ul>\n<li>\n<p>foo</p>\n<p>bar</p>\n</li>\n</ul>\n"),
        ("1.  foo\n\n    - bar\n",
         "<ol>\n<li>\n<p>foo</p>\n<ul>\n<li>bar</li>\n</ul>\n</li>\n</ol>\n"),
        ("    <a/>\n    *hi*\n\n    - one\n",
         "<pre><code>&lt;a/&gt;\n*hi*\n\n- one\n</code></pre>\n"),
        ("    chunk1\n\n    chunk2\n  \n \n \n    chunk3\n",
         "<pre><code>chunk1\n\nchunk2\n\n\n\nchunk3\n</code></pre>\n"),
        ("    chunk1\n      \n      chunk2\n", "<pre><code>chunk1\n  \n  chunk2\n</code></pre>\n"),
        ("Foo\n    bar\n", "<p>Foo\nbar</p>\n"),
        ("    foo\nbar\n", "<pre><code>foo\n</code></pre>\n<p>bar</p>\n"),
        ("# Heading\n    foo\nHeading\n------\n    foo\n----\n",
         "<h1>Heading</h1>\n<pre><code>foo\n</code></pre>\n<h2>Heading</h2>\n"
         "<pre><code>foo\n</code></pre>\n<hr />\n"),
        ("        foo\n    bar\n", "<pre><code>    foo\nbar\n</code></pre>\n"),
        ("\n    \n    foo\n    \n\n", "<pre><code>foo\n</code></pre>\n"),
        ("    foo  \n", "<pre><code>foo  \n</code></pre>\n"),
    ]

    def test_indented_code(self):
        self.check_cases()


class TestFencedCode(SpecCase):
    CASES = [
        ("```\n<\n >\n```\n", "<pre><code>&lt;\n &gt;\n</code></pre>\n"),
        ("~~~\n<\n >\n~~~\n", "<pre><code>&lt;\n &gt;\n</code></pre>\n"),
        ("``\nfoo\n``\n", "<p><code>foo</code></p>\n"),
        ("```\naaa\n~~~\n```\n", "<pre><code>aaa\n~~~\n</code></pre>\n"),
        ("~~~\naaa\n```\n~~~\n", "<pre><code>aaa\n```\n</code></pre>\n"),
        ("````\naaa\n```\n``````\n", "<pre><code>aaa\n```\n</code></pre>\n"),
        ("~~~~\naaa\n~~~\n~~~~\n", "<pre><code>aaa\n~~~\n</code></pre>\n"),
        ("```\n", "<pre><code></code></pre>\n"),
        ("`````\n\n```\naaa\n", "<pre><code>\n```\naaa\n</code></pre>\n"),
        ("> ```\n> aaa\n\nbbb\n",
         "<blockquote>\n<pre><code>aaa\n</code></pre>\n</blockquote>\n<p>bbb</p>\n"),
        ("```\n\n  \n```\n", "<pre><code>\n  \n</code></pre>\n"),
        ("```\n```\n", "<pre><code></code></pre>\n"),
        (" ```\n aaa\naaa\n```\n", "<pre><code>aaa\naaa\n</code></pre>\n"),
        ("  ```\naaa\n  aaa\naaa\n  ```\n", "<pre><code>aaa\naaa\naaa\n</code></pre>\n"),
        ("   ```\n   aaa\n    aaa\n  aaa\n   ```\n", "<pre><code>aaa\n aaa\naaa\n</code></pre>\n"),
        ("    ```\n    aaa\n    ```\n", "<pre><code>```\naaa\n```\n</code></pre>\n"),
        ("```\naaa\n  ```\n", "<pre><code>aaa\n</code></pre>\n"),
        ("   ```\naaa\n  ```\n", "<pre><code>aaa\n</code></pre>\n"),
        ("```\naaa\n    ```\n", "<pre><code>aaa\n    ```\n</code></pre>\n"),
        ("``` ```\naaa\n", "<p><code> </code>\naaa</p>\n"),
        ("~~~~~~\naaa\n~~~ ~~\n", "<pre><code>aaa\n~~~ ~~\n</code></pre>\n"),
        ("foo\n```\nbar\n```\nbaz\n", "<p>foo</p>\n<pre><code>bar\n</code></pre>\n<p>baz</p>\n"),
        ("foo\n---\n~~~\nbar\n~~~\n# baz\n",
         "<h2>foo</h2>\n<pre><code>bar\n</code></pre>\n<h1>baz</h1>\n"),
        ("```ruby\ndef foo(x)\n  return 3\nend\n```\n",
         "<pre><code class=\"language-ruby\">def foo(x)\n  return 3\nend\n</code></pre>\n"),
        ("~~~~    ruby startline=3 $%@#$\ndef foo(x)\n  return 3\nend\n~~~~~~~\n",
         "<pre><code class=\"language-ruby\">def foo(x)\n  return 3\nend\n</code></pre>\n"),
        ("````;\n````\n", "<pre><code class=\"language-;\"></code></pre>\n"),
        ("``` aa ```\nfoo\n", "<p><code>aa</code>\nfoo</p>\n"),
        ("~~~ aa ``` ~~~\nfoo\n~~~\n", "<pre><code class=\"language-aa\">foo\n</code></pre>\n"),
        ("```\n``` aaa\n```\n", "<pre><code>``` aaa\n</code></pre>\n"),
    ]

    def test_fenced_code(self):
        self.check_cases()


class TestHtmlBlocks(SpecCase):
    CASES = [
        ("<table><tr><td>\n<pre>\n**Hello**,\n\n_world_.\n</pre>\n</td></tr></table>\n",
         "<table><tr><td>\n<pre>\n**Hello**,\n<p><em>world</em>.\n</pre></p>\n</td></tr></table>\n"),
        ("<table>\n  <tr>\n    <td>\n           hi\n    </td>\n  </tr>\n</table>\n\nokay.\n",
         "<table>\n  <tr>\n    <td>\n           hi\n    </td>\n  </tr>\n</table>\n<p>okay.</p>\n"),
        (" <div>\n  *hello*\n         <foo><a>\n", " <div>\n  *hello*\n         <foo><a>\n"),
        ("</div>\n*foo*\n", "</div>\n*foo*\n"),
        ("<DIV CLASS=\"foo\">\n\n*Markdown*\n\n</DIV>\n",
         "<DIV CLASS=\"foo\">\n<p><em>Markdown</em></p>\n</DIV>\n"),
        ("<div id=\"foo\"\n  class=\"bar\">\n</div>\n", "<div id=\"foo\"\n  class=\"bar\">\n</div>\n"),
        ("<div id=\"foo\" class=\"bar\n  baz\">\n</div>\n",
         "<div id=\"foo\" class=\"bar\n  baz\">\n</div>\n"),
        ("<div>\n*foo*\n\n*bar*\n", "<div>\n*foo*\n<p><em>bar</em></p>\n"),
        ("<div id=\"foo\"\n*hi*\n", "<div id=\"foo\"\n*hi*\n"),
        ("<div class\nfoo\n", "<div class\nfoo\n"),
        ("<div *???-&&&-<---\n*foo*\n", "<div *???-&&&-<---\n*foo*\n"),
        ("<div><a href=\"bar\">*foo*</a></div>\n", "<div><a href=\"bar\">*foo*</a></div>\n"),
        ("<table><tr><td>\nfoo\n</td></tr></table>\n", "<table><tr><td>\nfoo\n</td></tr></table>\n"),
        ("<div></div>\n``` c\nint x = 33;\n```\n", "<div></div>\n``` c\nint x = 33;\n```\n"),
        ("<a href=\"foo\">\n*bar*\n</a>\n", "<a href=\"foo\">\n*bar*\n</a>\n"),
        ("<Warning>\n*bar*\n</Warning>\n", "<Warning>\n*bar*\n</Warning>\n"),
        ("<i class=\"foo\">\n*bar*\n</i>\n", "<i class=\"foo\">\n*bar*\n</i>\n"),
        ("</ins>\n*bar*\n", "</ins>\n*bar*\n"),
        ("<del>\n*foo*\n</del>\n", "<del>\n*foo*\n</del>\n"),
        ("<del>\n\n*foo*\n\n</del>\n", "<del>\n<p><em>foo</em></p>\n</del>\n"),
        ("<del>*foo*</del>\n", "<p><del><em>foo</em></del></p>\n"),
        ("<pre language=\"haskell\"><code>\nimport Text.HTML.TagSoup\n\nmain :: IO ()\n"
         "main = print $ parseTags tags\n</code></pre>\nokay\n",
         "<pre language=\"haskell\"><code>\nimport Text.HTML.TagSoup\n\nmain :: IO ()\n"
         "main = print $ parseTags tags\n</code></pre>\n<p>okay</p>\n"),
        ("<script type=\"text/javascript\">\n// JavaScript example\n\n"
         "document.getElementById(\"demo\").innerHTML = \"Hello JavaScript!\";\n</script>\nokay\n",
         "<script type=\"text/javascript\">\n// JavaScript example\n\n"
         "document.getElementById(\"demo\").innerHTML = \"Hello JavaScript!\";\n</script>\n"
         "<p>okay</p>\n"),
        ("<textarea>\n\n*foo*\n\n_bar_\n\n</textarea>\n",
         "<textarea>\n\n*foo*\n\n_bar_\n\n</textarea>\n"),
        ("<style\n  type=\"text/css\">\nh1 {color:red;}\n\np {color:blue;}\n</style>\nokay\n",
         "<style\n  type=\"text/css\">\nh1 {color:red;}\n\np {color:blue;}\n</style>\n<p>okay</p>\n"),
        ("<style\n  type=\"text/css\">\n\nfoo\n", "<style\n  type=\"text/css\">\n\nfoo\n"),
        ("> <div>\n> foo\n\nbar\n", "<blockquote>\n<div>\nfoo\n</blockquote>\n<p>bar</p>\n"),
        ("- <div>\n- foo\n", "<ul>\n<li>\n<div>\n</li>\n<li>foo</li>\n</ul>\n"),
        ("<style>p{color:red;}</style>\n*foo*\n",
         "<style>p{color:red;}</style>\n<p><em>foo</em></p>\n"),
        ("<!-- foo -->*bar*\n*baz*\n", "<!-- foo -->*bar*\n<p><em>baz</em></p>\n"),
        ("<script>\nfoo\n</script>1. *bar*\n", "<script>\nfoo\n</script>1. *bar*\n"),
        ("<!-- Foo\n\nbar\n   baz -->\nokay\n", "<!-- Foo\n\nbar\n   baz -->\n<p>okay</p>\n"),
        ("<?php\n\n  echo '>';\n\n?>\nokay\n", "<?php\n\n  echo '>';\n\n?>\n<p>okay</p>\n"),
        ("<!DOCTYPE html>\n", "<!DOCTYPE html>\n"),
        ("<![CDATA[\nfunction matchwo(a,b)\n{\n  if (a < b && a < 0) then {\n    return 1;\n\n"
         "  } else {\n\n    return 0;\n  }\n}\n]]>\nokay\n",
         "<![CDATA[\nfunction matchwo(a,b)\n{\n  if (a < b && a < 0) then {\n    return 1;\n\n"
         "  } else {\n\n    return 0;\n  }\n}\n]]>\n<p>okay</p>\n"),
        ("  <!-- foo -->\n\n    <!-- foo -->\n",
         "  <!-- foo -->\n<pre><code>&lt;!-- foo --&gt;\n</code></pre>\n"),
        ("  <div>\n\n    <div>\n", "  <div>\n<pre><code>&lt;div&gt;\n</code></pre>\n"),
        ("Foo\n<div>\nbar\n</div>\n", "<p>Foo</p>\n<div>\nbar\n</div>\n"),
        ("<div>\nbar\n</div>\n*foo*\n", "<div>\nbar\n</div>\n*foo*\n"),
        ("Foo\n<a href=\"bar\">\nbaz\n", "<p>Foo\n<a href=\"bar\">\nbaz</p>\n"),
        ("<div>\n\n*Emphasized* text.\n\n</div>\n",
         "<div>\n<p><em>Emphasized</em> text.</p>\n</div>\n"),
        ("<div>\n*Emphasized* text.\n</div>\n", "<div>\n*Emphasized* text.\n</div>\n"),
        ("<table>\n\n<tr>\n\n<td>\nHi\n</td>\n\n</tr>\n\n</table>\n",
         "<table>\n<tr>\n<td>\nHi\n</td>\n</tr>\n</table>\n"),
        ("<table>\n\n  <tr>\n\n    <td>\n      Hi\n    </td>\n\n  </tr>\n\n</table>\n",
         "<table>\n  <tr>\n<pre><code>&lt;td&gt;\n  Hi\n&lt;/td&gt;\n</code></pre>\n  </tr>\n</table>\n"),
    ]

    def test_html_blocks(self):
        self.check_cases()


class TestLinkReferenceDefinitions(SpecCase):
    CASES = [
        ("[foo]: /url \"title\"\n\n[foo]\n", "<p><a href=\"/url\" title=\"title\">foo</a></p>\n"),
        ("   [foo]: \n      /url  \n           'the title'  \n\n[foo]\n",
         "<p><a href=\"/url\" title=\"the title\">foo</a></p>\n"),
        ("[Foo*bar\\]]:my_(url) 'title (with parens)'\n\n[Foo*bar\\]]\n",
         "<p><a href=\"my_(url)\" title=\"title (with parens)\">Foo*bar]</a></p>\n"),
        ("[Foo bar]:\n<my url>\n'title'\n\n[Foo bar]\n",
         "<p><a href=\"my%20url\" title=\"title\">Foo bar</a></p>\n"),
        ("[foo]: /url '\ntitle\nline1\nline2\n'\n\n[foo]\n",
         "<p><a href=\"/url\" title=\"\ntitle\nline1\nline2\n\">foo</a></p>\n"),
        ("[foo]: /url 'title\n\nwith blank line'\n\n[foo]\n",
         "<p>[foo]: /url 'title</p>\n<p>with blank line'</p>\n<p>[foo]</p>\n"),
        ("[foo]:\n/url\n\n[foo]\n", "<p><a href=\"/url\">foo</a></p>\n"),
        ("[foo]:\n\n[foo]\n", "<p>[foo]:</p>\n<p>[foo]</p>\n"),
        ("[foo]: <>\n\n[foo]\n", "<p><a href=\"\">foo</a></p>\n"),
        ("[foo]: <bar>(baz)\n\n[foo]\n", "<p>[foo]: <bar>(baz)</p>\n<p>[foo]</p>\n"),
        ("[foo]: /url\\bar\\*baz \"foo\\\"bar\\baz\"\n\n[foo]\n",
         "<p><a href=\"/url%5Cbar*baz\" title=\"foo&quot;bar\\baz\">foo</a></p>\n"),
        ("[foo]\n\n[foo]: url\n", "<p><a href=\"url\">foo</a></p>\n"),
        ("[foo]\n\n[foo]: first\n[foo]: second\n", "<p><a href=\"first\">foo</a></p>\n"),
        ("[FOO]: /url\n\n[Foo]\n", "<p><a href=\"/url\">Foo</a></p>\n"),
        ("[\u0391\u0393\u03a9]: /\u03c6\u03bf\u03c5\n\n[\u03b1\u03b3\u03c9]\n",
         "<p><a href=\"/%CF%86%CE%BF%CF%85\">\u03b1\u03b3\u03c9</a></p>\n"),
        ("[foo]: /url\n", ""),
        ("[\nfoo\n]: /url\nbar\n", "<p>bar</p>\n"),
        ("[foo]: /url \"title\" ok\n", "<p>[foo]: /url &quot;title&quot; ok</p>\n"),
        ("[foo]: /url\n\"title\" ok\n", "<p>&quot;title&quot; ok</p>\n"),
        ("    [foo]: /url \"title\"\n\n[foo]\n",
         "<pre><code>[foo]: /url &quot;title&quot;\n</code></pre>\n<p>[foo]</p>\n"),
        ("```\n[foo]: /url\n```\n\n[foo]\n",
         "<pre><code>[foo]: /url\n</code></pre>\n<p>[foo]</p>\n"),
        ("Foo\n[bar]: /baz\n\n[bar]\n", "<p>Foo\n[bar]: /baz</p>\n<p>[bar]</p>\n"),
        ("# [Foo]\n[foo]: /url\n> bar\n",
         "<h1><a href=\"/url\">Foo</a></h1>\n<blockquote>\n<p>bar</p>\n</blockquote>\n"),
        ("[foo]: /url\nbar\n===\n[foo]\n", "<h1>bar</h1>\n<p><a href=\"/url\">foo</a></p>\n"),
        ("[foo]: /url\n===\n[foo]\n", "<p>===\n<a href=\"/url\">foo</a></p>\n"),
        ("[foo]: /foo-url \"foo\"\n[bar]: /bar-url\n  \"bar\"\n[baz]: /baz-url\n\n"
         "[foo],\n[bar],\n[baz]\n",
         "<p><a href=\"/foo-url\" title=\"foo\">foo</a>,\n"
         "<a href=\"/bar-url\" title=\"bar\">bar</a>,\n<a href=\"/baz-url\">baz</a></p>\n"),
        ("[foo]\n\n> [foo]: /url\n",
         "<p><a href=\"/url\">foo</a></p>\n<blockquote>\n</blockquote>\n"),
    ]

    def test_link_reference_definitions(self):
        self.check_cases()


class TestParagraphsAndBlankLines(SpecCase):
    CASES = [
        ("aaa\n\nbbb\n", "<p>aaa</p>\n<p>bbb</p>\n"),
        ("aaa\nbbb\n\nccc\nddd\n", "<p>aaa\nbbb</p>\n<p>ccc\nddd</p>\n"),
        ("aaa\n\n\nbbb\n", "<p>aaa</p>\n<p>bbb</p>\n"),
        ("  aaa\n bbb\n", "<p>aaa\nbbb</p>\n"),
        ("aaa\n             bbb\n                                       ccc\n",
         "<p>aaa\nbbb\nccc</p>\n"),
        ("   aaa\nbbb\n", "<p>aaa\nbbb</p>\n"),
        ("    aaa\nbbb\n", "<pre><code>aaa\n</code></pre>\n<p>bbb</p>\n"),
        ("aaa     \nbbb     \n", "<p>aaa<br />\nbbb</p>\n"),
        ("  \n\naaa\n  \n\n# aaa\n\n  \n", "<p>aaa</p>\n<h1>aaa</h1>\n"),
        ("", ""),
        ("\n\n", ""),
        ("foo\r\nbar\rbaz\n", "<p>foo\nbar\nbaz</p>\n"),
        ("a\u0000b\n", "<p>a\ufffdb</p>\n"),
    ]

    def test_paragraphs(self):
        self.check_cases()


class TestBlockQuotes(SpecCase):
    CASES = [
        ("> # Foo\n> bar\n> baz\n",
         "<blockquote>\n<h1>Foo</h1>\n<p>bar\nbaz</p>\n</blockquote>\n"),
        ("># Foo\n>bar\n> baz\n", "<blockquote>\n<h1>Foo</h1>\n<p>bar\nbaz</p>\n</blockquote>\n"),
        ("   > # Foo\n   > bar\n > baz\n",
         "<blockquote>\n<h1>Foo</h1>\n<p>bar\nbaz</p>\n</blockquote>\n"),
        ("    > # Foo\n    > bar\n    > baz\n",
         "<pre><code>&gt; # Foo\n&gt; bar\n&gt; baz\n</code></pre>\n"),
        ("> # Foo\n> bar\nbaz\n", "<blockquote>\n<h1>Foo</h1>\n<p>bar\nbaz</p>\n</blockquote>\n"),
        ("> bar\nbaz\n> foo\n", "<blockquote>\n<p>bar\nbaz\nfoo</p>\n</blockquote>\n"),
        ("> foo\n---\n", "<blockquote>\n<p>foo</p>\n</blockquote>\n<hr />\n"),
        ("> - foo\n- bar\n",
         "<blockquote>\n<ul>\n<li>foo</li>\n</ul>\n</blockquote>\n<ul>\n<li>bar</li>\n</ul>\n"),
        (">     foo\n    bar\n",
         "<blockquote>\n<pre><code>foo\n</code></pre>\n</blockquote>\n<pre><code>bar\n</code></pre>\n"),
        ("> ```\nfoo\n```\n",
         "<blockquote>\n<pre><code></code></pre>\n</blockquote>\n<p>foo</p>\n<pre><code></code></pre>\n"),
        ("> foo\n    - bar\n", "<blockquote>\n<p>foo\n- bar</p>\n</blockquote>\n"),
        (">\n", "<blockquote>\n</blockquote>\n"),
        (">\n>  \n> \n", "<blockquote>\n</blockquote>\n"),
        (">\n> foo\n>  \n", "<blockquote>\n<p>foo</p>\n</blockquote>\n"),
        ("> foo\n\n> bar\n",
         "<blockquote>\n<p>foo</p>\n</blockquote>\n<blockquote>\n<p>bar</p>\n</blockquote>\n"),
        ("> foo\n> bar\n", "<blockquote>\n<p>foo\nbar</p>\n</blockquote>\n"),
        ("> foo\n>\n> bar\n", "<blockquote>\n<p>foo</p>\n<p>bar</p>\n</blockquote>\n"),
        ("foo\n> bar\n", "<p>foo</p>\n<blockquote>\n<p>bar</p>\n</blockquote>\n"),
        ("> aaa\n***\n> bbb\n",
         "<blockquote>\n<p>aaa</p>\n</blockquote>\n<hr />\n<blockquote>\n<p>bbb</p>\n</blockquote>\n"),
        ("> bar\nbaz\n", "<blockquote>\n<p>bar\nbaz</p>\n</blockquote>\n"),
        ("> bar\n\nbaz\n", "<blockquote>\n<p>bar</p>\n</blockquote>\n<p>baz</p>\n"),
        ("> bar\n>\nbaz\n", "<blockquote>\n<p>bar</p>\n</blockquote>\n<p>baz</p>\n"),
        ("> > > foo\nbar\n",
         "<blockquote>\n<blockquote>\n<blockquote>\n<p>foo\nbar</p>\n</blockquote>\n"
         "</blockquote>\n</blockquote>\n"),
        (">>> foo\n> bar\n>>baz\n",
         "<blockquote>\n<blockquote>\n<blockquote>\n<p>foo\nbar\nbaz</p>\n</blockquote>\n"
         "</blockquote>\n</blockquote>\n"),
        (">     code\n\n>    not code\n",
         "<blockquote>\n<pre><code>code\n</code></pre>\n</blockquote>\n"
         "<blockquote>\n<p>not code</p>\n</blockquote>\n"),
    ]

    def test_block_quotes(self):
        self.check_cases()


class TestListItems(SpecCase):
    CASES = [
        ("A paragraph\nwith two lines.\n\n    indented code\n\n> A block quote.\n",
         "<p>A paragraph\nwith two lines.</p>\n<pre><code>indented code\n</code></pre>\n"
         "<blockquote>\n<p>A block quote.</p>\n</blockquote>\n"),
        ("1.  A paragraph\n    with two lines.\n\n        indented code\n\n    > A block quote.\n",
         "<ol>\n<li>\n<p>A paragraph\nwith two lines.</p>\n<pre><code>indented code\n</code></pre>\n"
         "<blockquote>\n<p>A block quote.</p>\n</blockquote>\n</li>\n</ol>\n"),
        ("- one\n\n two\n", "<ul>\n<li>one</li>\n</ul>\n<p>two</p>\n"),
        ("- one\n\n  two\n", "<ul>\n<li>\n<p>one</p>\n<p>two</p>\n</li>\n</ul>\n"),
        (" -    one\n\n     two\n", "<ul>\n<li>one</li>\n</ul>\n<pre><code> two\n</code></pre>\n"),
        (" -    one\n\n      two\n", "<ul>\n<li>\n<p>one</p>\n<p>two</p>\n</li>\n</ul>\n"),
        ("   > > 1.  one\n>>\n>>     two\n",
         "<blockquote>\n<blockquote>\n<ol>\n<li>\n<p>one</p>\n<p>two</p>\n</li>\n</ol>\n"
         "</blockquote>\n</blockquote>\n"),
        (">>- one\n>>\n  >  > two\n",
         "<blockquote>\n<blockquote>\n<ul>\n<li>one</li>\n</ul>\n<p>two</p>\n</blockquote>\n"
         "</blockquote>\n"),
        ("-one\n\n2.two\n", "<p>-one</p>\n<p>2.two</p>\n"),
        ("- foo\n\n\n  bar\n", "<ul>\n<li>\n<p>foo</p>\n<p>bar</p>\n</li>\n</ul>\n"),
        ("1.  foo\n\n    ```\n    bar\n    ```\n\n    baz\n\n    > bam\n",
         "<ol>\n<li>\n<p>foo</p>\n<pre><code>bar\n</code></pre>\n<p>baz</p>\n"
         "<blockquote>\n<p>bam</p>\n</blockquote>\n</li>\n</ol>\n"),
        ("- Foo\n\n      bar\n\n\n      baz\n",
         "<ul>\n<li>\n<p>Foo</p>\n<pre><code>bar\n\n\nbaz\n</code></pre>\n</li>\n</ul>\n"),
        ("123456789. ok\n", "<ol start=\"123456789\">\n<li>ok</li>\n</ol>\n"),
        ("1234567890. not ok\n", "<p>1234567890. not ok</p>\n"),
        ("0. ok\n", "<ol start=\"0\">\n<li>ok</li>\n</ol>\n"),
        ("003. ok\n", "<ol start=\"3\">\n<li>ok</li>\n</ol>\n"),
        ("-1. not ok\n", "<p>-1. not ok</p>\n"),
        ("- foo\n\n      bar\n",
         "<ul>\n<li>\n<p>foo</p>\n<pre><code>bar\n</code></pre>\n</li>\n</ul>\n"),
        ("  10.  foo\n\n           bar\n",
         "<ol start=\"10\">\n<li>\n<p>foo</p>\n<pre><code>bar\n</code></pre>\n</li>\n</ol>\n"),
        ("    indented code\n\nparagraph\n\n    more code\n",
         "<pre><code>indented code\n</code></pre>\n<p>paragraph</p>\n"
         "<pre><code>more code\n</code></pre>\n"),
        ("1.     indented code\n\n   paragraph\n\n       more code\n",
         "<ol>\n<li>\n<pre><code>indented code\n</code></pre>\n<p>paragraph</p>\n"
         "<pre><code>more code\n</code></pre>\n</li>\n</ol>\n"),
        ("1.      indented code\n\n   paragraph\n\n       more code\n",
         "<ol>\n<li>\n<pre><code> indented code\n</code></pre>\n<p>paragraph</p>\n"
         "<pre><code>more code\n</code></pre>\n</li>\n</ol>\n"),
        ("   foo\n\nbar\n", "<p>foo</p>\n<p>bar</p>\n"),
        ("-    foo\n\n  bar\n", "<ul>\n<li>foo</li>\n</ul>\n<p>bar</p>\n"),
        ("-  foo\n\n   bar\n", "<ul>\n<li>\n<p>foo</p>\n<p>bar</p>\n</li>\n</ul>\n"),
        ("-\n  foo\n-\n  ```\n  bar\n  ```\n-\n      baz\n",
         "<ul>\n<li>foo</li>\n<li>\n<pre><code>bar\n</code></pre>\n</li>\n"
         "<li>\n<pre><code>baz\n</code></pre>\n</li>\n</ul>\n"),
        ("-   \n  foo\n", "<ul>\n<li>foo</li>\n</ul>\n"),
        ("-\n\n  foo\n", "<ul>\n<li></li>\n</ul>\n<p>foo</p>\n"),
        ("- foo\n-\n- bar\n", "<ul>\n<li>foo</li>\n<li></li>\n<li>bar</li>\n</ul>\n"),
        ("- foo\n-   \n- bar\n", "<ul>\n<li>foo</li>\n<li></li>\n<li>bar</li>\n</ul>\n"),
        ("1. foo\n2.\n3. bar\n", "<ol>\n<li>foo</li>\n<li></li>\n<li>bar</li>\n</ol>\n"),
        ("*\n", "<ul>\n<li></li>\n</ul>\n"),
        ("foo\n*\n\nfoo\n1.\n", "<p>foo\n*</p>\n<p>foo\n1.</p>\n"),
        (" 1.  A paragraph\n     with two lines.\n\n         indented code\n\n     > A block quote.\n",
         "<ol>\n<li>\n<p>A paragraph\nwith two lines.</p>\n<pre><code>indented code\n</code></pre>\n"
         "<blockquote>\n<p>A block quote.</p>\n</blockquote>\n</li>\n</ol>\n"),
        ("    1.  A paragraph\n        with two lines.\n\n            indented code\n\n"
         "        > A block quote.\n",
         "<pre><code>1.  A paragraph\n    with two lines.\n\n        indented code\n\n"
         "    &gt; A block quote.\n</code></pre>\n"),
        ("  1.  A paragraph\nwith two lines.\n\n          indented code\n\n      > A block quote.\n",
         "<ol>\n<li>\n<p>A paragraph\nwith two lines.</p>\n<pre><code>indented code\n</code></pre>\n"
         "<blockquote>\n<p>A block quote.</p>\n</blockquote>\n</li>\n</ol>\n"),
        ("  1.  A paragraph\n    with two lines.\n",
         "<ol>\n<li>A paragraph\nwith two lines.</li>\n</ol>\n"),
        ("> 1. > Blockquote\ncontinued here.\n",
         "<blockquote>\n<ol>\n<li>\n<blockquote>\n<p>Blockquote\ncontinued here.</p>\n"
         "</blockquote>\n</li>\n</ol>\n</blockquote>\n"),
        ("> 1. > Blockquote\n> continued here.\n",
         "<blockquote>\n<ol>\n<li>\n<blockquote>\n<p>Blockquote\ncontinued here.</p>\n"
         "</blockquote>\n</li>\n</ol>\n</blockquote>\n"),
        ("- foo\n  - bar\n    - baz\n      - boo\n",
         "<ul>\n<li>foo\n<ul>\n<li>bar\n<ul>\n<li>baz\n<ul>\n<li>boo</li>\n</ul>\n</li>\n</ul>\n"
         "</li>\n</ul>\n</li>\n</ul>\n"),
        ("- foo\n - bar\n  - baz\n   - boo\n",
         "<ul>\n<li>foo</li>\n<li>bar</li>\n<li>baz</li>\n<li>boo</li>\n</ul>\n"),
        ("10) foo\n    - bar\n",
         "<ol start=\"10\">\n<li>foo\n<ul>\n<li>bar</li>\n</ul>\n</li>\n</ol>\n"),
        ("10) foo\n   - bar\n",
         "<ol start=\"10\">\n<li>foo</li>\n</ol>\n<ul>\n<li>bar</li>\n</ul>\n"),
        ("- - foo\n", "<ul>\n<li>\n<ul>\n<li>foo</li>\n</ul>\n</li>\n</ul>\n"),
        ("1. - 2. foo\n",
         "<ol>\n<li>\n<ul>\n<li>\n<ol start=\"2\">\n<li>foo</li>\n</ol>\n</li>\n</ul>\n</li>\n</ol>\n"),
        ("- # Foo\n- Bar\n  ---\n  baz\n",
         "<ul>\n<li>\n<h1>Foo</h1>\n</li>\n<li>\n<h2>Bar</h2>\nbaz</li>\n</ul>\n"),
    ]

    def test_list_items(self):
        self.check_cases()


class TestLists(SpecCase):
    CASES = [
        ("- foo\n- bar\n+ baz\n",
         "<ul>\n<li>foo</li>\n<li>bar</li>\n</ul>\n<ul>\n<li>baz</li>\n</ul>\n"),
        ("1. foo\n2. bar\n3) baz\n",
         "<ol>\n<li>foo</li>\n<li>bar</li>\n</ol>\n<ol start=\"3\">\n<li>baz</li>\n</ol>\n"),
        ("Foo\n- bar\n- baz\n", "<p>Foo</p>\n<ul>\n<li>bar</li>\n<li>baz</li>\n</ul>\n"),
        ("The number of windows in my house is\n14.  The number of doors is 6.\n",
         "<p>The number of windows in my house is\n14.  The number of doors is 6.</p>\n"),
        ("The number of windows in my house is\n1.  The number of doors is 6.\n",
         "<p>The number of windows in my house is</p>\n<ol>\n<li>The number of doors is 6.</li>\n</ol>\n"),
        ("- foo\n\n- bar\n\n\n- baz\n",
         "<ul>\n<li>\n<p>foo</p>\n</li>\n<li>\n<p>bar</p>\n</li>\n<li>\n<p>baz</p>\n</li>\n</ul>\n"),
        ("- foo\n  - bar\n    - baz\n\n\n      bim\n",
         "<ul>\n<li>foo\n<ul>\n<li>bar\n<ul>\n<li>\n<p>baz</p>\n<p>bim</p>\n</li>\n</ul>\n</li>\n"
         "</ul>\n</li>\n</ul>\n"),
        ("- foo\n- bar\n\n<!-- -->\n\n- baz\n- bim\n",
         "<ul>\n<li>foo</li>\n<li>bar</li>\n</ul>\n<!-- -->\n<ul>\n<li>baz</li>\n<li>bim</li>\n</ul>\n"),
        ("-   foo\n\n    notcode\n\n-   foo\n\n<!-- -->\n\n    code\n",
         "<ul>\n<li>\n<p>foo</p>\n<p>notcode</p>\n</li>\n<li>\n<p>foo</p>\n</li>\n</ul>\n"
         "<!-- -->\n<pre><code>code\n</code></pre>\n"),
        ("- a\n - b\n  - c\n   - d\n  - e\n - f\n- g\n",
         "<ul>\n<li>a</li>\n<li>b</li>\n<li>c</li>\n<li>d</li>\n<li>e</li>\n<li>f</li>\n"
         "<li>g</li>\n</ul>\n"),
        ("1. a\n\n  2. b\n\n   3. c\n",
         "<ol>\n<li>\n<p>a</p>\n</li>\n<li>\n<p>b</p>\n</li>\n<li>\n<p>c</p>\n</li>\n</ol>\n"),
        ("- a\n - b\n  - c\n   - d\n    - e\n",
         "<ul>\n<li>a</li>\n<li>b</li>\n<li>c</li>\n<li>d\n- e</li>\n</ul>\n"),
        ("1. a\n\n  2. b\n\n    3. c\n",
         "<ol>\n<li>\n<p>a</p>\n</li>\n<li>\n<p>b</p>\n</li>\n</ol>\n<pre><code>3. c\n</code></pre>\n"),
        ("- a\n- b\n\n- c\n",
         "<ul>\n<li>\n<p>a</p>\n</li>\n<li>\n<p>b</p>\n</li>\n<li>\n<p>c</p>\n</li>\n</ul>\n"),
        ("* a\n*\n\n* c\n",
         "<ul>\n<li>\n<p>a</p>\n</li>\n<li></li>\n<li>\n<p>c</p>\n</li>\n</ul>\n"),
        ("- a\n- b\n\n  c\n- d\n",
         "<ul>\n<li>\n<p>a</p>\n</li>\n<li>\n<p>b</p>\n<p>c</p>\n</li>\n<li>\n<p>d</p>\n</li>\n</ul>\n"),
        ("- a\n- b\n\n  [ref]: /url\n- d\n",
         "<ul>\n<li>\n<p>a</p>\n</li>\n<li>\n<p>b</p>\n</li>\n<li>\n<p>d</p>\n</li>\n</ul>\n"),
        ("- a\n- ```\n  b\n\n\n  ```\n- c\n",
         "<ul>\n<li>a</li>\n<li>\n<pre><code>b\n\n\n</code></pre>\n</li>\n<li>c</li>\n</ul>\n"),
        ("- a\n  - b\n\n    c\n- d\n",
         "<ul>\n<li>a\n<ul>\n<li>\n<p>b</p>\n<p>c</p>\n</li>\n</ul>\n</li>\n<li>d</li>\n</ul>\n"),
        ("* a\n  > b\n  >\n* c\n",
         "<ul>\n<li>a\n<blockquote>\n<p>b</p>\n</blockquote>\n</li>\n<li>c</li>\n</ul>\n"),
        ("- a\n  > b\n  ```\n  c\n  ```\n- d\n",
         "<ul>\n<li>a\n<blockquote>\n<p>b</p>\n</blockquote>\n<pre><code>c\n</code></pre>\n</li>\n"
         "<li>d</li>\n</ul>\n"),
        ("- a\n", "<ul>\n<li>a</li>\n</ul>\n"),
        ("- a\n  - b\n", "<ul>\n<li>a\n<ul>\n<li>b</li>\n</ul>\n</li>\n</ul>\n"),
        ("1. ```\n   foo\n   ```\n\n   bar\n",
         "<ol>\n<li>\n<pre><code>foo\n</code></pre>\n<p>bar</p>\n</li>\n</ol>\n"),
        ("* foo\n  * bar\n\n  baz\n",
         "<ul>\n<li>\n<p>foo</p>\n<ul>\n<li>bar</li>\n</ul>\n<p>baz</p>\n</li>\n</ul>\n"),
        ("- a\n  - b\n  - c\n\n- d\n  - e\n  - f\n",
         "<ul>\n<li>\n<p>a</p>\n<ul>\n<li>b</li>\n<li>c</li>\n</ul>\n</li>\n<li>\n<p>d</p>\n"
         "<ul>\n<li>e</li>\n<li>f</li>\n</ul>\n</li>\n</ul>\n"),
    ]

    def test_lists(self):
        self.check_cases()


class TestCodeSpans(SpecCase):
    CASES = [
        ("`hi`lo`\n", "<p><code>hi</code>lo`</p>\n"),
        ("`foo`\n", "<p><code>foo</code></p>\n"),
        ("`` foo ` bar ``\n", "<p><code>foo ` bar</code></p>\n"),
        ("` `` `\n", "<p><code>``</code></p>\n"),
        ("`  ``  `\n", "<p><code> `` </code></p>\n"),
        ("` a`\n", "<p><code> a</code></p>\n"),
        ("`\u00a0b\u00a0`\n", "<p><code>\u00a0b\u00a0</code></p>\n"),
        ("` `\n`  `\n", "<p><code> </code>\n<code>  </code></p>\n"),
        ("``\nfoo\nbar  \nbaz\n``\n", "<p><code>foo bar   baz</code></p>\n"),
        ("``\nfoo \n``\n", "<p><code>foo </code></p>\n"),
        ("`foo   bar \nbaz`\n", "<p><code>foo   bar  baz</code></p>\n"),
        ("`foo\\`bar`\n", "<p><code>foo\\</code>bar`</p>\n"),
        ("``foo`bar``\n", "<p><code>foo`bar</code></p>\n"),
        ("` foo `` bar `\n", "<p><code>foo `` bar</code></p>\n"),
        ("*foo`*`\n", "<p>*foo<code>*</code></p>\n"),
        ("[not a `link](/foo`)\n", "<p>[not a <code>link](/foo</code>)</p>\n"),
        ("`<a href=\"`\">`\n", "<p><code>&lt;a href=&quot;</code>&quot;&gt;`</p>\n"),
        ("<a href=\"`\">`\n", "<p><a href=\"`\">`</p>\n"),
        ("`<https://foo.bar.`baz>`\n", "<p><code>&lt;https://foo.bar.</code>baz&gt;`</p>\n"),
        ("<https://foo.bar.`baz>`\n",
         "<p><a href=\"https://foo.bar.%60baz\">https://foo.bar.`baz</a>`</p>\n"),
        ("```foo``\n", "<p>```foo``</p>\n"),
        ("`foo\n", "<p>`foo</p>\n"),
        ("`foo``bar``\n", "<p>`foo<code>bar</code></p>\n"),
    ]

    def test_code_spans(self):
        self.check_cases()


class TestEmphasis(SpecCase):
    CASES = [
        ("*foo bar*\n", "<p><em>foo bar</em></p>\n"),
        ("a * foo bar*\n", "<p>a * foo bar*</p>\n"),
        ("a*\"foo\"*\n", "<p>a*&quot;foo&quot;*</p>\n"),
        ("*\u00a0a\u00a0*\n", "<p>*\u00a0a\u00a0*</p>\n"),
        ("*$*alpha.\n\n*\u00a3*bravo.\n\n*\u20ac*charlie.\n",
         "<p>*$*alpha.</p>\n<p>*\u00a3*bravo.</p>\n<p>*\u20ac*charlie.</p>\n"),
        ("foo*bar*\n", "<p>foo<em>bar</em></p>\n"),
        ("5*6*78\n", "<p>5<em>6</em>78</p>\n"),
        ("_foo bar_\n", "<p><em>foo bar</em></p>\n"),
        ("_ foo bar_\n", "<p>_ foo bar_</p>\n"),
        ("a_\"foo\"_\n", "<p>a_&quot;foo&quot;_</p>\n"),
        ("foo_bar_\n", "<p>foo_bar_</p>\n"),
        ("5_6_78\n", "<p>5_6_78</p>\n"),
        ("\u043f\u0440\u0438\u0441\u0442\u0430\u043d\u044f\u043c_\u0441\u0442\u0440\u0435\u043c\u044f\u0442\u0441\u044f_\n",
         "<p>\u043f\u0440\u0438\u0441\u0442\u0430\u043d\u044f\u043c_\u0441\u0442\u0440\u0435\u043c\u044f\u0442\u0441\u044f_</p>\n"),
        ("aa_\"bb\"_cc\n", "<p>aa_&quot;bb&quot;_cc</p>\n"),
        ("foo-_(bar)_\n", "<p>foo-<em>(bar)</em></p>\n"),
        ("_foo*\n", "<p>_foo*</p>\n"),
        ("*foo bar *\n", "<p>*foo bar *</p>\n"),
        ("*foo bar\n*\n", "<p>*foo bar\n*</p>\n"),
        ("*(*foo)\n", "<p>*(*foo)</p>\n"),
        ("*(*foo*)*\n", "<p><em>(<em>foo</em>)</em></p>\n"),
        ("*foo*bar\n", "<p><em>foo</em>bar</p>\n"),
        ("_foo bar _\n", "<p>_foo bar _</p>\n"),
        ("_(_foo)\n", "<p>_(_foo)</p>\n"),
        ("_(_foo_)_\n", "<p><em>(<em>foo</em>)</em></p>\n"),
        ("_foo_bar\n", "<p>_foo_bar</p>\n"),
        ("_foo_bar_baz_\n", "<p><em>foo_bar_baz</em></p>\n"),
        ("_(bar)_.\n", "<p><em>(bar)</em>.</p>\n"),
        ("**foo bar**\n", "<p><strong>foo bar</strong></p>\n"),
        ("** foo bar**\n", "<p>** foo bar**</p>\n"),
        ("a**\"foo\"**\n", "<p>a**&quot;foo&quot;**</p>\n"),
        ("foo**bar**\n", "<p>foo<strong>bar</strong></p>\n"),
        ("__foo bar__\n", "<p><strong>foo bar</strong></p>\n"),
        ("__ foo bar__\n", "<p>__ foo bar__</p>\n"),
        ("__\nfoo bar__\n", "<p>__\nfoo bar__</p>\n"),
        ("a__\"foo\"__\n", "<p>a__&quot;foo&quot;__</p>\n"),
        ("foo__bar__\n", "<p>foo__bar__</p>\n"),
        ("5__6__78\n", "<p>5__6__78</p>\n"),
        ("__foo, __bar__, baz__\n", "<p><strong>foo, <strong>bar</strong>, baz</strong></p>\n"),
        ("foo-__(bar)__\n", "<p>foo-<strong>(bar)</strong></p>\n"),
        ("**foo bar **\n", "<p>**foo bar **</p>\n"),
        ("**(**foo)\n", "<p>**(**foo)</p>\n"),
        ("*(**foo**)*\n", "<p><em>(<strong>foo</strong>)</em></p>\n"),
        ("**Gomphocarpus (*Gomphocarpus physocarpus*, syn.\n*Asclepias physocarpa*)**\n",
         "<p><strong>Gomphocarpus (<em>Gomphocarpus physocarpus</em>, syn.\n"
         "<em>Asclepias physocarpa</em>)</strong></p>\n"),
        ("**foo \"*bar*\" foo**\n", "<p><strong>foo &quot;<em>bar</em>&quot; foo</strong></p>\n"),
        ("**foo**bar\n", "<p><strong>foo</strong>bar</p>\n"),
        ("__foo bar __\n", "<p>__foo bar __</p>\n"),
        ("__(__foo)\n", "<p>__(__foo)</p>\n"),
        ("_(__foo__)_\n", "<p><em>(<strong>foo</strong>)</em></p>\n"),
        ("__foo__bar\n", "<p>__foo__bar</p>\n"),
        ("__foo__bar__baz__\n", "<p><strong>foo__bar__baz</strong></p>\n"),
        ("__(bar)__.\n", "<p><strong>(bar)</strong>.</p>\n"),
        ("*foo [bar](/url)*\n", "<p><em>foo <a href=\"/url\">bar</a></em></p>\n"),
        ("*foo\nbar*\n", "<p><em>foo\nbar</em></p>\n"),
        ("_foo __bar__ baz_\n", "<p><em>foo <strong>bar</strong> baz</em></p>\n"),
        ("_foo _bar_ baz_\n", "<p><em>foo <em>bar</em> baz</em></p>\n"),
        ("__foo_ bar_\n", "<p><em><em>foo</em> bar</em></p>\n"),
        ("*foo *bar**\n", "<p><em>foo <em>bar</em></em></p>\n"),
        ("*foo **bar** baz*\n", "<p><em>foo <strong>bar</strong> baz</em></p>\n"),
        ("*foo**bar**baz*\n", "<p><em>foo<strong>bar</strong>baz</em></p>\n"),
        ("*foo**bar*\n", "<p><em>foo**bar</em></p>\n"),
        ("***foo** bar*\n", "<p><em><strong>foo</strong> bar</em></p>\n"),
        ("*foo **bar***\n", "<p><em>foo <strong>bar</strong></em></p>\n"),
        ("*foo**bar***\n", "<p><em>foo<strong>bar</strong></em></p>\n"),
        ("foo***bar***baz\n", "<p>foo<em><strong>bar</strong></em>baz</p>\n"),
        ("foo******bar*********baz\n",
         "<p>foo<strong><strong><strong>bar</strong></strong></strong>***baz</p>\n"),
        ("*foo **bar *baz* bim** bop*\n",
         "<p><em>foo <strong>bar <em>baz</em> bim</strong> bop</em></p>\n"),
        ("*foo [*bar*](/url)*\n", "<p><em>foo <a href=\"/url\"><em>bar</em></a></em></p>\n"),
        ("** is not an empty emphasis\n", "<p>** is not an empty emphasis</p>\n"),
        ("**** is not an empty strong emphasis\n", "<p>**** is not an empty strong emphasis</p>\n"),
        ("**foo [bar](/url)**\n", "<p><strong>foo <a href=\"/url\">bar</a></strong></p>\n"),
        ("**foo\nbar**\n", "<p><strong>foo\nbar</strong></p>\n"),
        ("__foo _bar_ baz__\n", "<p><strong>foo <em>bar</em> baz</strong></p>\n"),
        ("__foo __bar__ baz__\n", "<p><strong>foo <strong>bar</strong> baz</strong></p>\n"),
        ("____foo__ bar__\n", "<p><strong><strong>foo</strong> bar</strong></p>\n"),
        ("**foo **bar****\n", "<p><strong>foo <strong>bar</strong></strong></p>\n"),
        ("**foo *bar* baz**\n", "<p><strong>foo <em>bar</em> baz</strong></p>\n"),
        ("**foo*bar*baz**\n", "<p><strong>foo<em>bar</em>baz</strong></p>\n"),
        ("***foo* bar**\n", "<p><strong><em>foo</em> bar</strong></p>\n"),
        ("**foo *bar***\n", "<p><strong>foo <em>bar</em></strong></p>\n"),
        ("**foo *bar **baz**\nbim* bop**\n",
         "<p><strong>foo <em>bar <strong>baz</strong>\nbim</em> bop</strong></p>\n"),
        ("**foo [*bar*](/url)**\n",
         "<p><strong>foo <a href=\"/url\"><em>bar</em></a></strong></p>\n"),
        ("__ is not an empty emphasis\n", "<p>__ is not an empty emphasis</p>\n"),
        ("____ is not an empty strong emphasis\n", "<p>____ is not an empty strong emphasis</p>\n"),
        ("foo ***\n", "<p>foo ***</p>\n"),
        ("foo *\\**\n", "<p>foo <em>*</em></p>\n"),
        ("foo *_*\n", "<p>foo <em>_</em></p>\n"),
        ("foo *****\n", "<p>foo *****</p>\n"),
        ("foo **\\***\n", "<p>foo <strong>*</strong></p>\n"),
        ("foo **_**\n", "<p>foo <strong>_</strong></p>\n"),
        ("**foo*\n", "<p>*<em>foo</em></p>\n"),
        ("*foo**\n", "<p><em>foo</em>*</p>\n"),
        ("***foo**\n", "<p>*<strong>foo</strong></p>\n"),
        ("****foo*\n", "<p>***<em>foo</em></p>\n"),
        ("**foo***\n", "<p><strong>foo</strong>*</p>\n"),
        ("*foo****\n", "<p><em>foo</em>***</p>\n"),
        ("foo ___\n", "<p>foo ___</p>\n"),
        ("foo _\\__\n", "<p>foo <em>_</em></p>\n"),
        ("foo _*_\n", "<p>foo <em>*</em></p>\n"),
        ("foo _____\n", "<p>foo _____</p>\n"),
        ("foo __\\___\n", "<p>foo <strong>_</strong></p>\n"),
        ("foo __*__\n", "<p>foo <strong>*</strong></p>\n"),
        ("__foo_\n", "<p>_<em>foo</em></p>\n"),
        ("_foo__\n", "<p><em>foo</em>_</p>\n"),
        ("___foo__\n", "<p>_<strong>foo</strong></p>\n"),
        ("____foo_\n", "<p>___<em>foo</em></p>\n"),
        ("__foo___\n", "<p><strong>foo</strong>_</p>\n"),
        ("_foo____\n", "<p><em>foo</em>___</p>\n"),
        ("**foo**\n", "<p><strong>foo</strong></p>\n"),
        ("*_foo_*\n", "<p><em><em>foo</em></em></p>\n"),
        ("__foo__\n", "<p><strong>foo</strong></p>\n"),
        ("_*foo*_\n", "<p><em><em>foo</em></em></p>\n"),
        ("****foo****\n", "<p><strong><strong>foo</strong></strong></p>\n"),
        ("____foo____\n", "<p><strong><strong>foo</strong></strong></p>\n"),
        ("******foo******\n", "<p><strong><strong><strong>foo</strong></strong></strong></p>\n"),
        ("***foo***\n", "<p><em><strong>foo</strong></em></p>\n"),
        ("_____foo_____\n", "<p><em><strong><strong>foo</strong></strong></em></p>\n"),
        ("*foo _bar* baz_\n", "<p><em>foo _bar</em> baz_</p>\n"),
        ("*foo __bar *baz bim__ bam*\n", "<p><em>foo <strong>bar *baz bim</strong> bam</em></p>\n"),
        ("**foo **bar baz**\n", "<p>**foo <strong>bar baz</strong></p>\n"),
        ("*foo *bar baz*\n", "<p>*foo <em>bar baz</em></p>\n"),
        ("*[bar*](/url)\n", "<p>*<a href=\"/url\">bar*</a></p>\n"),
        ("_foo [bar_](/url)\n", "<p>_foo <a href=\"/url\">bar_</a></p>\n"),
        ("*<img src=\"foo\" title=\"*\"/>\n", "<p>*<img src=\"foo\" title=\"*\"/></p>\n"),
        ("**<a href=\"**\">\n", "<p>**<a href=\"**\"></p>\n"),
        ("__<a href=\"__\">\n", "<p>__<a href=\"__\"></p>\n"),
        ("*a `*`*\n", "<p><em>a <code>*</code></em></p>\n"),
        ("_a `_`_\n", "<p><em>a <code>_</code></em></p>\n"),
        ("**a<https://foo.bar/?q=**>\n",
         "<p>**a<a href=\"https://foo.bar/?q=**\">https://foo.bar/?q=**</a></p>\n"),
        ("__a<https://foo.bar/?q=__>\n",
         "<p>__a<a href=\"https://foo.bar/?q=__\">https://foo.bar/?q=__</a></p>\n"),
    ]

    def test_emphasis(self):
        self.check_cases()


class TestLinks(SpecCase):
    CASES = [
        ("[link](/uri \"title\")\n", "<p><a href=\"/uri\" title=\"title\">link</a></p>\n"),
        ("[link](/uri)\n", "<p><a href=\"/uri\">link</a></p>\n"),
        ("[](./target.md)\n", "<p><a href=\"./target.md\"></a></p>\n"),
        ("[link]()\n", "<p><a href=\"\">link</a></p>\n"),
        ("[link](<>)\n", "<p><a href=\"\">link</a></p>\n"),
        ("[]()\n", "<p><a href=\"\"></a></p>\n"),
        ("[link](/my uri)\n", "<p>[link](/my uri)</p>\n"),
        ("[link](</my uri>)\n", "<p><a href=\"/my%20uri\">link</a></p>\n"),
        ("[link](foo\nbar)\n", "<p>[link](foo\nbar)</p>\n"),
        ("[link](<foo\nbar>)\n", "<p>[link](<foo\nbar>)</p>\n"),
        ("[a](<b)c>)\n", "<p><a href=\"b)c\">a</a></p>\n"),
        ("[link](<foo\\>)\n", "<p>[link](&lt;foo&gt;)</p>\n"),
        ("[a](<b)c\n[a](<b)c>\n[a](<b>c)\n",
         "<p>[a](&lt;b)c\n[a](&lt;b)c&gt;\n[a](<b>c)</p>\n"),
        ("[link](\\(foo\\))\n", "<p><a href=\"(foo)\">link</a></p>\n"),
        ("[link](foo(and(bar)))\n", "<p><a href=\"foo(and(bar))\">link</a></p>\n"),
        ("[link](foo(and(bar))\n", "<p>[link](foo(and(bar))</p>\n"),
        ("[link](foo\\(and\\(bar\\))\n", "<p><a href=\"foo(and(bar)\">link</a></p>\n"),
        ("[link](<foo(and(bar)>)\n", "<p><a href=\"foo(and(bar)\">link</a></p>\n"),
        ("[link](foo\\)\\:)\n", "<p><a href=\"foo):\">link</a></p>\n"),
        ("[link](#fragment)\n\n[link](https://example.com#fragment)\n\n"
         "[link](https://example.com?foo=3#frag)\n",
         "<p><a href=\"#fragment\">link</a></p>\n"
         "<p><a href=\"https://example.com#fragment\">link</a></p>\n"
         "<p><a href=\"https://example.com?foo=3#frag\">link</a></p>\n"),
        ("[link](foo\\bar)\n", "<p><a href=\"foo%5Cbar\">link</a></p>\n"),
        ("[link](foo%20b&auml;)\n", "<p><a href=\"foo%20b%C3%A4\">link</a></p>\n"),
        ("[link](\"title\")\n", "<p><a href=\"%22title%22\">link</a></p>\n"),
        ("[link](/url \"title\")\n[link](/url 'title')\n[link](/url (title))\n",
         "<p><a href=\"/url\" title=\"title\">link</a>\n"
         "<a href=\"/url\" title=\"title\">link</a>\n"
         "<a href=\"/url\" title=\"title\">link</a></p>\n"),
        ("[link](/url \"title \\\"&quot;\")\n",
         "<p><a href=\"/url\" title=\"title &quot;&quot;\">link</a></p>\n"),
        ("[link](/url\u00a0\"title\")\n",
         "<p><a href=\"/url%C2%A0%22title%22\">link</a></p>\n"),
        ("[link](/url \"title \"and\" title\")\n",
         "<p>[link](/url &quot;title &quot;and&quot; title&quot;)</p>\n"),
        ("[link](/url 'title \"and\" title')\n",
         "<p><a href=\"/url\" title=\"title &quot;and&quot; title\">link</a></p>\n"),
        ("[link](   /uri\n  \"title\"  )\n", "<p><a href=\"/uri\" title=\"title\">link</a></p>\n"),
        ("[link] (/uri)\n", "<p>[link] (/uri)</p>\n"),
        ("[link [foo [bar]]](/uri)\n", "<p><a href=\"/uri\">link [foo [bar]]</a></p>\n"),
        ("[link] bar](/uri)\n", "<p>[link] bar](/uri)</p>\n"),
        ("[link [bar](/uri)\n", "<p>[link <a href=\"/uri\">bar</a></p>\n"),
        ("[link \\[bar](/uri)\n", "<p><a href=\"/uri\">link [bar</a></p>\n"),
        ("[link *foo **bar** `#`*](/uri)\n",
         "<p><a href=\"/uri\">link <em>foo <strong>bar</strong> <code>#</code></em></a></p>\n"),
        ("[![moon](moon.jpg)](/uri)\n",
         "<p><a href=\"/uri\"><img src=\"moon.jpg\" alt=\"moon\" /></a></p>\n"),
        ("[foo [bar](/uri)](/uri)\n", "<p>[foo <a href=\"/uri\">bar</a>](/uri)</p>\n"),
        ("[foo *[bar [baz](/uri)](/uri)*](/uri)\n",
         "<p>[foo <em>[bar <a href=\"/uri\">baz</a>](/uri)</em>](/uri)</p>\n"),
        ("![[[foo](uri1)](uri2)](uri3)\n", "<p><img src=\"uri3\" alt=\"[foo](uri2)\" /></p>\n"),
        ("*[foo*](/uri)\n", "<p>*<a href=\"/uri\">foo*</a></p>\n"),
        ("[foo *bar](baz*)\n", "<p><a href=\"baz*\">foo *bar</a></p>\n"),
        ("*foo [bar* baz]\n", "<p><em>foo [bar</em> baz]</p>\n"),
        ("[foo <bar attr=\"](baz)\">\n", "<p>[foo <bar attr=\"](baz)\"></p>\n"),
        ("[foo`](/uri)`\n", "<p>[foo<code>](/uri)</code></p>\n"),
        ("[foo<https://example.com/?search=](uri)>\n",
         "<p>[foo<a href=\"https://example.com/?search=%5D(uri)\">"
         "https://example.com/?search=](uri)</a></p>\n"),
        ("[foo][bar]\n\n[bar]: /url \"title\"\n",
         "<p><a href=\"/url\" title=\"title\">foo</a></p>\n"),
        ("[link [foo [bar]]][ref]\n\n[ref]: /uri\n",
         "<p><a href=\"/uri\">link [foo [bar]]</a></p>\n"),
        ("[link \\[bar][ref]\n\n[ref]: /uri\n", "<p><a href=\"/uri\">link [bar</a></p>\n"),
        ("[link *foo **bar** `#`*][ref]\n\n[ref]: /uri\n",
         "<p><a href=\"/uri\">link <em>foo <strong>bar</strong> <code>#</code></em></a></p>\n"),
        ("[![moon](moon.jpg)][ref]\n\n[ref]: /uri\n",
         "<p><a href=\"/uri\"><img src=\"moon.jpg\" alt=\"moon\" /></a></p>\n"),
        ("[foo [bar](/uri)][ref]\n\n[ref]: /uri\n",
         "<p>[foo <a href=\"/uri\">bar</a>]<a href=\"/uri\">ref</a></p>\n"),
        ("[foo *bar [baz][ref]*][ref]\n\n[ref]: /uri\n",
         "<p>[foo <em>bar <a href=\"/uri\">baz</a></em>]<a href=\"/uri\">ref</a></p>\n"),
        ("*[foo*][ref]\n\n[ref]: /uri\n", "<p>*<a href=\"/uri\">foo*</a></p>\n"),
        ("[foo *bar][ref]*\n\n[ref]: /uri\n", "<p><a href=\"/uri\">foo *bar</a>*</p>\n"),
        ("[foo <bar attr=\"][ref]\">\n\n[ref]: /uri\n", "<p>[foo <bar attr=\"][ref]\"></p>\n"),
        ("[foo`][ref]`\n\n[ref]: /uri\n", "<p>[foo<code>][ref]</code></p>\n"),
        ("[foo<https://example.com/?search=][ref]>\n\n[ref]: /uri\n",
         "<p>[foo<a href=\"https://example.com/?search=%5D%5Bref%5D\">"
         "https://example.com/?search=][ref]</a></p>\n"),
        ("[foo][BaR]\n\n[bar]: /url \"title\"\n",
         "<p><a href=\"/url\" title=\"title\">foo</a></p>\n"),
        ("[\u1e9e]\n\n[SS]: /url\n", "<p><a href=\"/url\">\u1e9e</a></p>\n"),
        ("[Foo\n  bar]: /url\n\n[Baz][Foo bar]\n", "<p><a href=\"/url\">Baz</a></p>\n"),
        ("[foo] [bar]\n\n[bar]: /url \"title\"\n",
         "<p>[foo] <a href=\"/url\" title=\"title\">bar</a></p>\n"),
        ("[foo]\n[bar]\n\n[bar]: /url \"title\"\n",
         "<p>[foo]\n<a href=\"/url\" title=\"title\">bar</a></p>\n"),
        ("[foo]: /url1\n\n[foo]: /url2\n\n[bar][foo]\n", "<p><a href=\"/url1\">bar</a></p>\n"),
        ("[bar][foo\\!]\n\n[foo!]: /url\n", "<p>[bar][foo!]</p>\n"),
        ("[foo][ref[]\n\n[ref[]: /uri\n", "<p>[foo][ref[]</p>\n<p>[ref[]: /uri</p>\n"),
        ("[foo][ref[bar]]\n\n[ref[bar]]: /uri\n",
         "<p>[foo][ref[bar]]</p>\n<p>[ref[bar]]: /uri</p>\n"),
        ("[[[foo]]]\n\n[[[foo]]]: /url\n", "<p>[[[foo]]]</p>\n<p>[[[foo]]]: /url</p>\n"),
        ("[foo][ref\\[]\n\n[ref\\[]: /uri\n", "<p><a href=\"/uri\">foo</a></p>\n"),
        ("[bar\\\\]: /uri\n\n[bar\\\\]\n", "<p><a href=\"/uri\">bar\\</a></p>\n"),
        ("[]\n\n[]: /uri\n", "<p>[]</p>\n<p>[]: /uri</p>\n"),
        ("[\n ]\n\n[\n ]: /uri\n", "<p>[\n]</p>\n<p>[\n]: /uri</p>\n"),
        ("[foo][]\n\n[foo]: /url \"title\"\n",
         "<p><a href=\"/url\" title=\"title\">foo</a></p>\n"),
        ("[*foo* bar][]\n\n[*foo* bar]: /url \"title\"\n",
         "<p><a href=\"/url\" title=\"title\"><em>foo</em> bar</a></p>\n"),
        ("[Foo][]\n\n[foo]: /url \"title\"\n",
         "<p><a href=\"/url\" title=\"title\">Foo</a></p>\n"),
        ("[foo] \n[]\n\n[foo]: /url \"title\"\n",
         "<p><a href=\"/url\" title=\"title\">foo</a>\n[]</p>\n"),
        ("[foo]\n\n[foo]: /url \"title\"\n", "<p><a href=\"/url\" title=\"title\">foo</a></p>\n"),
        ("[*foo* bar]\n\n[*foo* bar]: /url \"title\"\n",
         "<p><a href=\"/url\" title=\"title\"><em>foo</em> bar</a></p>\n"),
        ("[[*foo* bar]]\n\n[*foo* bar]: /url \"title\"\n",
         "<p>[<a href=\"/url\" title=\"title\"><em>foo</em> bar</a>]</p>\n"),
        ("[[bar [foo]\n\n[foo]: /url\n", "<p>[[bar <a href=\"/url\">foo</a></p>\n"),
        ("[Foo]\n\n[foo]: /url \"title\"\n", "<p><a href=\"/url\" title=\"title\">Foo</a></p>\n"),
        ("[foo] bar\n\n[foo]: /url\n", "<p><a href=\"/url\">foo</a> bar</p>\n"),
        ("\\[foo]\n\n[foo]: /url \"title\"\n", "<p>[foo]</p>\n"),
        ("[foo*]: /url\n\n*[foo*]\n", "<p>*<a href=\"/url\">foo*</a></p>\n"),
        ("[foo][bar]\n\n[foo]: /url1\n[bar]: /url2\n", "<p><a href=\"/url2\">foo</a></p>\n"),
        ("[foo][]\n\n[foo]: /url1\n", "<p><a href=\"/url1\">foo</a></p>\n"),
        ("[foo]()\n\n[foo]: /url1\n", "<p><a href=\"\">foo</a></p>\n"),
        ("[foo](not a link)\n\n[foo]: /url1\n",
         "<p><a href=\"/url1\">foo</a>(not a link)</p>\n"),
        ("[foo][bar][baz]\n\n[baz]: /url\n", "<p>[foo]<a href=\"/url\">bar</a></p>\n"),
        ("[foo][bar][baz]\n\n[baz]: /url1\n[bar]: /url2\n",
         "<p><a href=\"/url2\">foo</a><a href=\"/url1\">baz</a></p>\n"),
        ("[foo][bar][baz]\n\n[baz]: /url1\n[foo]: /url2\n",
         "<p>[foo]<a href=\"/url1\">bar</a></p>\n"),
    ]

    def test_links(self):
        self.check_cases()


class TestImages(SpecCase):
    CASES = [
        ("![foo](/url \"title\")\n", "<p><img src=\"/url\" alt=\"foo\" title=\"title\" /></p>\n"),
        ("![foo *bar*]\n\n[foo *bar*]: train.jpg \"train & tracks\"\n",
         "<p><img src=\"train.jpg\" alt=\"foo bar\" title=\"train &amp; tracks\" /></p>\n"),
        ("![foo ![bar](/url)](/url2)\n", "<p><img src=\"/url2\" alt=\"foo bar\" /></p>\n"),
        ("![foo [bar](/url)](/url2)\n", "<p><img src=\"/url2\" alt=\"foo bar\" /></p>\n"),
        ("![foo *bar*][]\n\n[foo *bar*]: train.jpg \"train & tracks\"\n",
         "<p><img src=\"train.jpg\" alt=\"foo bar\" title=\"train &amp; tracks\" /></p>\n"),
        ("![foo *bar*][foobar]\n\n[FOOBAR]: train.jpg \"train & tracks\"\n",
         "<p><img src=\"train.jpg\" alt=\"foo bar\" title=\"train &amp; tracks\" /></p>\n"),
        ("![foo](train.jpg)\n", "<p><img src=\"train.jpg\" alt=\"foo\" /></p>\n"),
        ("My ![foo bar](/path/to/train.jpg  \"title\"   )\n",
         "<p>My <img src=\"/path/to/train.jpg\" alt=\"foo bar\" title=\"title\" /></p>\n"),
        ("![foo](<url>)\n", "<p><img src=\"url\" alt=\"foo\" /></p>\n"),
        ("![](/url)\n", "<p><img src=\"/url\" alt=\"\" /></p>\n"),
        ("![foo][bar]\n\n[bar]: /url\n", "<p><img src=\"/url\" alt=\"foo\" /></p>\n"),
        ("![foo][bar]\n\n[BAR]: /url\n", "<p><img src=\"/url\" alt=\"foo\" /></p>\n"),
        ("![foo][]\n\n[foo]: /url \"title\"\n",
         "<p><img src=\"/url\" alt=\"foo\" title=\"title\" /></p>\n"),
        ("![*foo* bar][]\n\n[*foo* bar]: /url \"title\"\n",
         "<p><img src=\"/url\" alt=\"foo bar\" title=\"title\" /></p>\n"),
        ("![Foo][]\n\n[foo]: /url \"title\"\n",
         "<p><img src=\"/url\" alt=\"Foo\" title=\"title\" /></p>\n"),
        ("![foo] \n[]\n\n[foo]: /url \"title\"\n",
         "<p><img src=\"/url\" alt=\"foo\" title=\"title\" />\n[]</p>\n"),
        ("![foo]\n\n[foo]: /url \"title\"\n",
         "<p><img src=\"/url\" alt=\"foo\" title=\"title\" /></p>\n"),
        ("![*foo* bar]\n\n[*foo* bar]: /url \"title\"\n",
         "<p><img src=\"/url\" alt=\"foo bar\" title=\"title\" /></p>\n"),
        ("![[foo]]\n\n[[foo]]: /url \"title\"\n",
         "<p>![[foo]]</p>\n<p>[[foo]]: /url &quot;title&quot;</p>\n"),
        ("![Foo]\n\n[foo]: /url \"title\"\n",
         "<p><img src=\"/url\" alt=\"Foo\" title=\"title\" /></p>\n"),
        ("!\\[foo]\n\n[foo]: /url \"title\"\n", "<p>![foo]</p>\n"),
        ("\\![foo]\n\n[foo]: /url \"title\"\n",
         "<p>!<a href=\"/url\" title=\"title\">foo</a></p>\n"),
    ]

    def test_images(self):
        self.check_cases()


class TestAutolinks(SpecCase):
    CASES = [
        ("<http://foo.bar.baz>\n",
         "<p><a href=\"http://foo.bar.baz\">http://foo.bar.baz</a></p>\n"),
        ("<https://foo.bar.baz/test?q=hello&id=22&boolean>\n",
         "<p><a href=\"https://foo.bar.baz/test?q=hello&amp;id=22&amp;boolean\">"
         "https://foo.bar.baz/test?q=hello&amp;id=22&amp;boolean</a></p>\n"),
        ("<irc://foo.bar:2233/baz>\n",
         "<p><a href=\"irc://foo.bar:2233/baz\">irc://foo.bar:2233/baz</a></p>\n"),
        ("<MAILTO:FOO@BAR.BAZ>\n", "<p><a href=\"MAILTO:FOO@BAR.BAZ\">MAILTO:FOO@BAR.BAZ</a></p>\n"),
        ("<a+b+c:d>\n", "<p><a href=\"a+b+c:d\">a+b+c:d</a></p>\n"),
        ("<made-up-scheme://foo,bar>\n",
         "<p><a href=\"made-up-scheme://foo,bar\">made-up-scheme://foo,bar</a></p>\n"),
        ("<https://../>\n", "<p><a href=\"https://../\">https://../</a></p>\n"),
        ("<localhost:5001/foo>\n", "<p><a href=\"localhost:5001/foo\">localhost:5001/foo</a></p>\n"),
        ("<https://foo.bar/baz bim>\n", "<p>&lt;https://foo.bar/baz bim&gt;</p>\n"),
        ("<https://example.com/\\[\\>\n",
         "<p><a href=\"https://example.com/%5C%5B%5C\">https://example.com/\\[\\</a></p>\n"),
        ("<foo@bar.example.com>\n",
         "<p><a href=\"mailto:foo@bar.example.com\">foo@bar.example.com</a></p>\n"),
        ("<foo+special@Bar.baz-bar0.com>\n",
         "<p><a href=\"mailto:foo+special@Bar.baz-bar0.com\">foo+special@Bar.baz-bar0.com</a></p>\n"),
        ("<foo\\+@bar.example.com>\n", "<p>&lt;foo+@bar.example.com&gt;</p>\n"),
        ("<>\n", "<p>&lt;&gt;</p>\n"),
        ("< https://foo.bar >\n", "<p>&lt; https://foo.bar &gt;</p>\n"),
        ("<m:abc>\n", "<p>&lt;m:abc&gt;</p>\n"),
        ("<foo.bar.baz>\n", "<p>&lt;foo.bar.baz&gt;</p>\n"),
        ("https://example.com\n", "<p>https://example.com</p>\n"),
        ("foo@bar.example.com\n", "<p>foo@bar.example.com</p>\n"),
    ]

    def test_autolinks(self):
        self.check_cases()


class TestRawHtml(SpecCase):
    CASES = [
        ("<a><bab><c2c>\n", "<p><a><bab><c2c></p>\n"),
        ("<a/><b2/>\n", "<p><a/><b2/></p>\n"),
        ("<a  /><b2\ndata=\"foo\" >\n", "<p><a  /><b2\ndata=\"foo\" ></p>\n"),
        ("<a foo=\"bar\" bam = 'baz <em>\"</em>'\n_boolean zoop:33=zoop:33 />\n",
         "<p><a foo=\"bar\" bam = 'baz <em>\"</em>'\n_boolean zoop:33=zoop:33 /></p>\n"),
        ("Foo <responsive-image src=\"foo.jpg\" />\n",
         "<p>Foo <responsive-image src=\"foo.jpg\" /></p>\n"),
        ("<33> <__>\n", "<p>&lt;33&gt; &lt;__&gt;</p>\n"),
        ("<a h*#ref=\"hi\">\n", "<p>&lt;a h*#ref=&quot;hi&quot;&gt;</p>\n"),
        ("<a href=\"hi'> <a href=hi'>\n", "<p>&lt;a href=&quot;hi'&gt; &lt;a href=hi'&gt;</p>\n"),
        ("< a><\nfoo><bar/ >\n<foo bar=baz\nbim!bop />\n",
         "<p>&lt; a&gt;&lt;\nfoo&gt;&lt;bar/ &gt;\n&lt;foo bar=baz\nbim!bop /&gt;</p>\n"),
        ("<a href='bar'title=title>\n", "<p>&lt;a href='bar'title=title&gt;</p>\n"),
        ("</a></foo >\n", "<p></a></foo ></p>\n"),
        ("</a href=\"foo\">\n", "<p>&lt;/a href=&quot;foo&quot;&gt;</p>\n"),
        ("foo <!-- this is a --\ncomment - with hyphens -->\n",
         "<p>foo <!-- this is a --\ncomment - with hyphens --></p>\n"),
        ("foo <!--> foo -->\n\nfoo <!---> foo -->\n",
         "<p>foo <!--> foo --&gt;</p>\n<p>foo <!---> foo --&gt;</p>\n"),
        ("foo <?php echo $a; ?>\n", "<p>foo <?php echo $a; ?></p>\n"),
        ("foo <!ELEMENT br EMPTY>\n", "<p>foo <!ELEMENT br EMPTY></p>\n"),
        ("foo <![CDATA[>&<]]>\n", "<p>foo <![CDATA[>&<]]></p>\n"),
        ("foo <a href=\"&ouml;\">\n", "<p>foo <a href=\"&ouml;\"></p>\n"),
        ("foo <a href=\"\\*\">\n", "<p>foo <a href=\"\\*\"></p>\n"),
        ("<a href=\"\\\"\">\n", "<p>&lt;a href=&quot;&quot;&quot;&gt;</p>\n"),
    ]

    def test_raw_html(self):
        self.check_cases()


class TestLineBreaksAndText(SpecCase):
    CASES = [
        ("foo  \nbaz\n", "<p>foo<br />\nbaz</p>\n"),
        ("foo\\\nbaz\n", "<p>foo<br />\nbaz</p>\n"),
        ("foo       \nbaz\n", "<p>foo<br />\nbaz</p>\n"),
        ("foo  \n     bar\n", "<p>foo<br />\nbar</p>\n"),
        ("foo\\\n     bar\n", "<p>foo<br />\nbar</p>\n"),
        ("*foo  \nbar*\n", "<p><em>foo<br />\nbar</em></p>\n"),
        ("*foo\\\nbar*\n", "<p><em>foo<br />\nbar</em></p>\n"),
        ("`code  \nspan`\n", "<p><code>code   span</code></p>\n"),
        ("`code\\\nspan`\n", "<p><code>code\\ span</code></p>\n"),
        ("<a href=\"foo  \nbar\">\n", "<p><a href=\"foo  \nbar\"></p>\n"),
        ("<a href=\"foo\\\nbar\">\n", "<p><a href=\"foo\\\nbar\"></p>\n"),
        ("foo\\\n", "<p>foo\\</p>\n"),
        ("foo  \n", "<p>foo</p>\n"),
        ("### foo\\\n", "<h3>foo\\</h3>\n"),
        ("### foo  \n", "<h3>foo</h3>\n"),
        ("foo\nbaz\n", "<p>foo\nbaz</p>\n"),
        ("foo \n baz\n", "<p>foo\nbaz</p>\n"),
        ("hello $.;'there\n", "<p>hello $.;'there</p>\n"),
        ("Foo \u03c7\u03c1\u1fc6\u03bd\n", "<p>Foo \u03c7\u03c1\u1fc6\u03bd</p>\n"),
        ("Multiple     spaces\n", "<p>Multiple     spaces</p>\n"),
    ]

    def test_line_breaks_and_text(self):
        self.check_cases()


class TestApi(unittest.TestCase):
    def test_outcome_example(self):
        self.assertEqual(render('# Hi\n\n*a* **b**\n'),
                         '<h1>Hi</h1>\n<p><em>a</em> <strong>b</strong></p>\n')

    def test_modules_expose_parsers(self):
        doc = blocks.parse('> a\n')
        self.assertEqual(doc.first_child.type, 'block_quote')
        self.assertEqual(inlines.normalize_uri('a b\u00e4'), 'a%20b%C3%A4')
        self.assertEqual(inlines.normalize_reference('[ Foo\n  BAR ]'), 'foo bar')

    def test_deeply_nested_input_does_not_crash(self):
        html = render('> ' * 300 + 'x\n')
        self.assertEqual(html.count('<blockquote>'), 300)
        html = render('*' * 5000 + 'a' + '*' * 5000 + '\n')
        self.assertTrue(html.startswith('<p>'))
        html = render('[' * 3000 + 'a' + ']' * 3000 + '\n')
        self.assertTrue(html.startswith('<p>'))


class TestCli(unittest.TestCase):
    def test_cli_calls_render(self):
        stdin = io.TextIOWrapper(io.BytesIO('# Hi\n'.encode('utf-8')), encoding='utf-8')
        stdout = io.TextIOWrapper(io.BytesIO(), encoding='utf-8')
        with mock.patch.object(cli, 'render', wraps=cli.render) as spy, \
                mock.patch.object(sys, 'stdin', stdin), \
                mock.patch.object(sys, 'stdout', stdout):
            rc = cli.main()
            stdout.flush()
            output = stdout.buffer.getvalue().decode('utf-8')
        self.assertEqual(rc, 0)
        spy.assert_called_once_with('# Hi\n')
        self.assertEqual(output, '<h1>Hi</h1>\n')

    def test_cli_subprocess(self):
        md = '# Hi\n\n*a* **b**\n\n- x\n- y\n'
        proc = subprocess.run([sys.executable, '-m', 'src.cli'], input=md.encode('utf-8'),
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=ROOT,
                              timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode('utf-8', 'replace'))
        self.assertEqual(proc.stdout.decode('utf-8'), render(md))
        self.assertEqual(proc.stdout.decode('utf-8'),
                         '<h1>Hi</h1>\n<p><em>a</em> <strong>b</strong></p>\n'
                         '<ul>\n<li>x</li>\n<li>y</li>\n</ul>\n')


if __name__ == '__main__':
    unittest.main()
