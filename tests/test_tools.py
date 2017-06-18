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
import pytest


def test_sbin_added_to_path():
    from diffoscope.tools import tool_required

    @tool_required(os.listdir('/sbin')[0])
    def fn():
        pass

    fn()


def test_required_tool_not_found():
    from diffoscope.exc import RequiredToolNotFound
    from diffoscope.tools import tool_required

    @tool_required('does-not-exist')
    def fn():
        pass

    with pytest.raises(RequiredToolNotFound):
        fn()
