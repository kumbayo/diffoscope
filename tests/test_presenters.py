# -*- coding: utf-8 -*-
#
# diffoscope: in-depth comparison of files, archives, and directories
#
# Copyright © 2017 Chris Lamb <lamby@debian.org>
#
# diffoscope is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# diffoscope is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with diffoscope.  If not, see <https://www.gnu.org/licenses/>.

import os
import re
import pytest

from diffoscope.main import main
from diffoscope.presenters.utils import create_limited_print_func, PrintLimitReached, PartialString

from .utils.data import cwd_data, get_data
from .utils.tools import skip_unless_tools_exist

re_html = re.compile(r'.*<body(?P<body>.*)<div class="footer">', re.MULTILINE | re.DOTALL)


def run(capsys, *args, pair=('test1.tar', 'test2.tar')):
    with pytest.raises(SystemExit) as exc, cwd_data():
        main(args + pair)
    out, err = capsys.readouterr()

    assert err == ''
    assert exc.value.code == 1
    return out

def run_images(capsys, *args):
    return run(capsys, *args, pair=('test1.png', 'test2.png'))

def extract_body(val):
    """
    Extract the salient parts of HTML fixtures that won't change between
    versions, etc.
    """

    result = re_html.search(val).group('body')

    # Ensure that we extracted something
    assert len(result) > 0

    return result

def test_text_option_is_default(capsys):
    out = run(capsys)

    assert out == get_data('output.txt')

def test_text_proper_indentation(capsys):
    out = run(capsys, pair=('archive1.tar', 'archive2.tar'))

    assert out == get_data('archive12.diff.txt')

def test_text_option_color(capsys):
    out = run(capsys, '--text-color=always')

    assert out == get_data('output.colored.txt')

def test_text_option_with_file(tmpdir, capsys):
    report_path = str(tmpdir.join('report.txt'))

    out = run(capsys, '--text', report_path)

    assert out == ''

    with open(report_path, 'r', encoding='utf-8') as f:
        assert f.read() == get_data('output.txt')

def test_text_option_with_stdiout(capsys):
    out = run(capsys, '--text', '-')

    assert out == get_data('output.txt')

def test_markdown(capsys):
    out = run(capsys, '--markdown', '-')

    assert out == get_data('output.md')

def test_restructuredtext(capsys):
    out = run(capsys, '--restructured-text', '-')

    assert out == get_data('output.rst')

def test_json(capsys):
    out = run(capsys, '--json', '-')

    assert out == get_data('output.json')

def test_no_report_option(capsys):
    out = run(capsys)

    assert out == get_data('output.txt')

def test_html_option_with_file(tmpdir, capsys):
    report_path = str(tmpdir.join('report.html'))

    out = run(capsys, '--html', report_path)

    assert out == ''
    with open(report_path, 'r', encoding='utf-8') as f:
        body = extract_body(f.read())
        assert body.count('div class="difference"') == 4

@skip_unless_tools_exist('compare', 'convert')
def test_html_visuals(tmpdir, capsys):
    report_path = str(tmpdir.join('report.html'))

    out = run_images(capsys, '--html', report_path)

    assert out == ''
    body = extract_body(open(report_path, 'r', encoding='utf-8').read())
    assert '<img src="data:image/png;base64' in body
    assert '<img src="data:image/gif;base64' in body

def test_htmldir_option(tmpdir, capsys):
    html_dir = os.path.join(str(tmpdir), 'target')

    out = run(capsys, '--html-dir', html_dir, '--jquery', 'disable')

    assert out == ''
    assert os.path.isdir(html_dir)
    with open(os.path.join(html_dir, 'index.html'), 'r', encoding='utf-8') as f:
        body = extract_body(f.read())
        assert body.count('div class="difference"') == 4

def test_html_option_with_stdout(capsys):
    body = extract_body(run(capsys, '--html', '-'))

    assert body.count('div class="difference"') == 4

def test_limited_print():
    fake = lambda x: None
    with pytest.raises(PrintLimitReached):
        p = create_limited_print_func(fake, 5)
        p("123456")
    with pytest.raises(PrintLimitReached):
        p = create_limited_print_func(fake, 5)
        p("123")
        p("456")
    p = create_limited_print_func(fake, 5)
    p("123")
    p("456", force=True)

def test_partial_string():
    a, b = object(), object()
    tmpl = PartialString("{0} {1}", a, b)
    assert tmpl.holes == (a, b)
    assert tmpl.format({a: "Hello,", b: "World!"}) == 'Hello, World!'
    assert tmpl.pformat({a: "Hello,"}) == PartialString('Hello, {0}', b)
    assert tmpl.pformat({b: "World!"}) == PartialString('{0} World!', a)
    assert tmpl.base_len, tmpl.num_holes == (1, 2)
    assert tmpl.size(hole_size=33) == 67
    assert tmpl.pformat({a: PartialString('{0}', b)}) == PartialString('{0} {0}', b)
    assert tmpl.pformat({a: tmpl}) == PartialString('{0} {1} {1}', a, b)
    assert tmpl.pformat({b: tmpl}) == PartialString('{0} {0} {1}', a, b)
    PartialString("{1}", a, b)
    with pytest.raises(IndexError):
        PartialString("{0} {1} {2}", a, b)

def test_partial_string_cont():
    t, cont = PartialString.cont()
    t = cont(t, "x: {0}\ny: {1}\n{-1}", object(), object())
    t = cont(t, "z: {0}\n{-1}", object())
    t = cont(t, "")
    key = t.holes
    assert (t.format({key[0]: "line1", key[1]: "line2", key[2]: "line3"})
            == 'x: line1\ny: line2\nz: line3\n')
    assert t.size(hole_size=5) == 27

def test_partial_string_numl():
    tmpl = PartialString.numl("{0} {1} {2}", 2, object())
    assert tmpl.holes[:2] == (0, 1)
    assert tmpl.pformatl("(1)", "(2)", "(o)") == PartialString('(1) (2) (o)')

def test_partial_string_escape():
    tmpl = PartialString.numl("find {0} -name {1} " +
               PartialString.escape("-exec ls -la {} \;"), 2)
    assert tmpl == PartialString('find {0} -name {1} -exec ls -la {{}} \\;', *tmpl.holes)
    assert tmpl.size() == 33
    assert tmpl.size(4) == 39
    assert tmpl == PartialString.numl("find {0} -name {1} -exec ls -la {2} \;", 3).pformat({2: "{}"})

    assert (tmpl.pformatl("my{}path", "my{}file") ==
        PartialString('find my{{}}path -name my{{}}file -exec ls -la {{}} \\;'))
    assert (tmpl.formatl("my{}path", "my{}file") ==
        'find my{}path -name my{}file -exec ls -la {} \\;')

    esc = PartialString("{{}} {0}", None)
    assert esc.pformat({None: PartialString.of(None)}) == esc
    assert esc.format({None: "0"}) == "{} 0"
    with pytest.raises(ValueError):
        PartialString("{}")
