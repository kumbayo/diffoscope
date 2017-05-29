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

from .utils.data import cwd_data, get_data

re_html = re.compile(r'.*<body(?P<body>.*)<div class="footer">', re.MULTILINE | re.DOTALL)
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')


def run(capsys, *args):
    with pytest.raises(SystemExit) as exc, cwd_data():
        main(args + ('test1.tar', 'test2.tar'))
    out, err = capsys.readouterr()

    assert err == ''
    assert exc.value.code == 1
    return out

def run_images(capsys, *args):
    with pytest.raises(SystemExit) as exc, cwd_data():
        main(args + ('test1.png', 'test2.png'))
    out, err = capsys.readouterr()

    assert err == ''
    assert exc.value.code == 1
    return out

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
        assert extract_body(f.read()) == extract_body(get_data('output.html'))

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
        assert extract_body(f.read()) == extract_body(get_data('index.html'))

def test_html_option_with_stdout(capsys):
    out = run(capsys, '--html', '-')

    assert extract_body(out) == extract_body(get_data('output.html'))
