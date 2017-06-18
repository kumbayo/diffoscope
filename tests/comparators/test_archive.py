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

from ..utils.data import load_fixture


archive1 = load_fixture('archive1.tar')
archive2 = load_fixture('archive2.tar')

@pytest.fixture
def differences(archive1, archive2):
    return archive1.compare(archive2).details

def test_compressed_content_name(differences):
    assert differences[1].details[1].source1 == 'compressed'
    assert differences[1].details[1].source2 == 'compressed'
