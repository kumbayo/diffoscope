# -*- coding: utf-8 -*-
#
# diffoscope: in-depth comparison of files, archives, and directories
#
# Copyright © 2017 Ximin Luo <infinity0@debian.org>
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
from diffoscope.comparators.utils.compare import compare_root_paths
from diffoscope.readers import load_diff_from_path

from .utils.data import cwd_data, get_data


def run_read_write(capsys, diff, *args):
    with pytest.raises(SystemExit) as exc, cwd_data():
        main(args + (diff,))

    out, err = capsys.readouterr()

    assert err == ''
    assert exc.value.code == 1
    assert out == get_data(diff) # presented-output is same as parsed-input
    return out

def run_diff_read(diffpath):
    with cwd_data():
        diff = compare_root_paths('test1.tar', 'test2.tar')
        read = load_diff_from_path(diffpath)
    assert diff.equals(read)

def test_json(capsys):
    run_read_write(capsys, 'output.json', '--json', '-')
    run_diff_read('output.json')
