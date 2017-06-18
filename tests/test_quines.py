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

from diffoscope.comparators.deb import DebFile
from diffoscope.comparators.zip import ZipFile
from diffoscope.comparators.gzip import GzipFile

from .utils.data import load_fixture, get_data

quine1 = load_fixture('quine.gz')
quine2 = load_fixture('quine.zip')
quine3 = load_fixture('quine_a.deb')
quine4 = load_fixture('quine_b.deb')

"""
Check that we are not recursively unpacking the quines in an infinite loop. See
<https://research.swtch.com/zip> and <https://bugs.debian.org/780761>.
"""


def test_identification(quine1, quine2):
    assert isinstance(quine1, GzipFile)
    assert isinstance(quine2, ZipFile)


def test_no_differences(quine1):
    difference = quine1.compare(quine1)
    assert difference is None


@pytest.fixture
def differences(quine1, quine2):
    return quine1.compare(quine2).details


def test_difference(differences):
    expected_diff = get_data('quine_expected_diff')
    assert differences[0].unified_diff == expected_diff


def test_identification_deb(quine3, quine4):
    assert isinstance(quine3, DebFile)
    assert isinstance(quine4, DebFile)


@pytest.fixture
def differences_deb(quine3, quine4):
    return quine3.compare(quine4).details


def test_differences_deb(differences_deb):
    expected_diff = get_data('quine_deb_expected_diff')
    assert differences_deb[0].unified_diff == expected_diff
