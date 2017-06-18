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

from diffoscope.comparators.pcap import PcapFile

from ..utils.data import load_fixture, get_data
from ..utils.tools import skip_unless_tools_exist
from ..utils.nonexisting import assert_non_existing

pcap1 = load_fixture('test1.pcap')
pcap2 = load_fixture('test2.pcap')


def test_identification(pcap1):
    assert isinstance(pcap1, PcapFile)


def test_no_differences(pcap1):
    difference = pcap1.compare(pcap1)
    assert difference is None


@pytest.fixture
def differences(pcap1, pcap2):
    return pcap1.compare(pcap2).details


@skip_unless_tools_exist('tcpdump')
def test_diff(differences):
    expected_diff = get_data('pcap_expected_diff')
    assert differences[0].unified_diff == expected_diff


@skip_unless_tools_exist('tcpdump')
def test_compare_non_existing(monkeypatch, pcap1):
    assert_non_existing(monkeypatch, pcap1, has_null_source=False)
