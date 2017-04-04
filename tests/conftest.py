# -*- coding: utf-8 -*-
#
# diffoscope: in-depth comparison of files, archives, and directories
#
# Copyright © 2016 Brett Smith <debbug@brettcsmith.org>
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

from diffoscope.path import set_path
from diffoscope.locale import set_locale
from diffoscope.progress import ProgressManager
from diffoscope.comparators import ComparatorManager


def pytest_configure(config):
    # Ensure set_path fixture runs before all tests.
    set_path()


@pytest.fixture(autouse=True, scope='session')
def locale():
    # Ensure set_locale fixture runs before each test.
    set_locale()


@pytest.fixture(autouse=True)
def reload_comparators():
    # Reload Comparators after every test so we are always in a consistent
    # state
    ComparatorManager().reload()


@pytest.fixture(autouse=True)
def reset_progress():
    ProgressManager().reset()
