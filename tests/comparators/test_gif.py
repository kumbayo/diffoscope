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

import pytest

from diffoscope.comparators.gif import GifFile
from diffoscope.config import Config

from ..utils.data import load_fixture, get_data
from ..utils.tools import skip_unless_tools_exist
from ..utils.nonexisting import assert_non_existing

gif1 = load_fixture('test1.gif')
gif2 = load_fixture('test2.gif')
gif3 = load_fixture('test3.gif')
gif4 = load_fixture('test4.gif')


def test_identification(gif1):
    assert isinstance(gif1, GifFile)

def test_no_differences(gif1):
    difference = gif1.compare(gif1)
    assert difference is None

@pytest.fixture
def differences(gif1, gif2):
    return gif1.compare(gif2).details

@skip_unless_tools_exist('gifbuild')
def test_diff(differences):
    expected_diff = get_data('gif_expected_diff')
    assert differences[0].unified_diff == expected_diff

@skip_unless_tools_exist('gifbuild')
def test_compare_non_existing(monkeypatch, gif1):
    assert_non_existing(monkeypatch, gif1, has_null_source=False)

@skip_unless_tools_exist('gifbuild', 'compose', 'convert', 'identify')
def test_has_visuals(monkeypatch, gif3, gif4):
    monkeypatch.setattr(Config(), 'compute_visual_diffs', True)
    gif_diff = gif3.compare(gif4)
    assert len(gif_diff.details) == 2
    assert len(gif_diff.details[1].visuals) == 2
    assert gif_diff.details[1].visuals[0].data_type == 'image/png;base64'
    assert gif_diff.details[1].visuals[1].data_type == 'image/gif;base64'

@skip_unless_tools_exist('gifbuild', 'compose', 'convert', 'identify')
def test_no_visuals_different_size(monkeypatch, gif1, gif2):
    monkeypatch.setattr(Config(), 'compute_visual_diffs', True)
    gif_diff = gif1.compare(gif2)
    assert len(gif_diff.details) == 1
    assert len(gif_diff.details[0].visuals) == 0
