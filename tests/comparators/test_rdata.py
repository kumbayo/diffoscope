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

import pytest

from diffoscope.comparators.gzip import GzipFile

from ..utils import diff_ignore_line_numbers
from ..utils.data import load_fixture, get_data
from ..utils.tools import skip_unless_tools_exist
from ..utils.nonexisting import assert_non_existing


file1 = load_fixture('test1.rdx')
file2 = load_fixture('test2.rdx')

def test_identification(file1):
    assert isinstance(file1, GzipFile)

def test_no_differences(file1):
    difference = file1.compare(file1)
    assert difference is None

@pytest.fixture
def differences(file1, file2):
    return file1.compare(file2).details

@skip_unless_tools_exist('Rscript')
def test_num_items(differences):
    assert len(differences) == 1

@skip_unless_tools_exist('Rscript')
def test_item_rds(differences):
    assert differences[0].source1 == 'test1.rdx-content'
    assert differences[0].source2 == 'test2.rdx-content'
    expected_diff = get_data('rds_expected_diff')
    assert differences[0].details[0].unified_diff == expected_diff
