# -*- coding: utf-8 -*-
#
# diffoscope: in-depth comparison of files, archives, and directories
#
# Copyright © 2017 Juliana Rodrigues <juliana.orod@gmail.com>
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

from diffoscope.comparators.xml import XMLFile

from ..utils.data import load_fixture, get_data


xml_a = load_fixture('test1.xml')
xml_b = load_fixture('test2.xml')
invalid_xml = load_fixture('test_invalid.xml')


def test_identification(xml_a):
    assert isinstance(xml_a, XMLFile)


def test_invalid(invalid_xml):
    assert not isinstance(invalid_xml, XMLFile)


def test_no_differences(xml_a):
    assert xml_a.compare(xml_a) is None


@pytest.fixture
def differences(xml_a, xml_b):
    return xml_a.compare(xml_b).details


def test_diff(differences):
    expected_diff = get_data('test_xml_expected_diff')
    assert differences[0].unified_diff == expected_diff
