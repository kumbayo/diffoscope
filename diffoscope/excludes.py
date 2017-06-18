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

import fnmatch
import logging
import re

from diffoscope.config import Config

logger = logging.getLogger(__name__)


def command_excluded(command):
    for y in Config().exclude_commands:
        if re.search(y, command):
            logger.debug("Excluding command '%s' as it matches pattern '%s'", command, y)
            return True
    return False

def filter_excludes(filenames):
    for x in filenames:
        for y in Config().excludes:
            if fnmatch.fnmatchcase(x, y):
                logger.debug("Excluding %s as it matches pattern '%s'", x, y)
                break
        else:
            yield x

def any_excluded(*filenames):
    for x in filenames:
        for y in Config().excludes:
            if fnmatch.fnmatchcase(x, y):
                return True
    return False
