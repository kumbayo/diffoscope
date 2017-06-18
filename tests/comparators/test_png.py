# -*- coding: utf-8 -*-
#
# diffoscope: in-depth comparison of files, archives, and directories
#
# Copyright © 2015 Jérémy Bobbio <lunar@debian.org>
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

from diffoscope.comparators.png import PngFile
from diffoscope.config import Config

from ..utils.data import load_fixture, get_data
from ..utils.tools import skip_unless_tools_exist
from ..utils.nonexisting import assert_non_existing


png1 = load_fixture('test1.png')
png2 = load_fixture('test2.png')

def test_identification(png1):
    assert isinstance(png1, PngFile)

def test_no_differences(png1):
    difference = png1.compare(png1)
    assert difference is None

@pytest.fixture
def differences(png1, png2):
    return png1.compare(png2).details

@skip_unless_tools_exist('sng')
def test_diff(differences):
    expected_diff = get_data('png_expected_diff')
    assert differences[0].unified_diff == expected_diff

@skip_unless_tools_exist('sng')
def test_compare_non_existing(monkeypatch, png1):
    assert_non_existing(monkeypatch, png1, has_null_source=False)

@skip_unless_tools_exist('sng', 'compose', 'convert', 'identify')
def test_has_visuals(monkeypatch, png1, png2):
    monkeypatch.setattr(Config(), 'compute_visual_diffs', True)
    png_diff = png1.compare(png2)
    assert len(png_diff.details) == 2
    assert len(png_diff.details[1].visuals) == 2
    assert png_diff.details[1].visuals[0].data_type == 'image/png;base64'
    assert png_diff.details[1].visuals[1].data_type == 'image/gif;base64'
