# -*- coding: utf-8 -*-
#
# diffoscope: in-depth comparison of files, archives, and directories
#
# Copyright © 2016 Chris Lamb <lamby@debian.org>
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
import collections
import platform
import functools

from distutils.spawn import find_executable

from .profiling import profile

# Memoize calls to ``distutils.spawn.find_executable`` to avoid excessive stat
# calls
find_executable = functools.lru_cache()(find_executable)

# The output of --help and --list-tools will use the order of this dict.
# Please keep it alphabetized.
OS_NAMES = collections.OrderedDict([
    ('arch', 'Arch Linux'),
    ('debian', 'Debian'),
    ('FreeBSD', 'FreeBSD'),
])

# Ensure tests and the runtime environment can locate binaries in /usr/sbin
# (eg. tcpdump). We must modify the path before the @tool_required decorator is
# applied.
pathlist = os.environ['PATH'].split(os.pathsep)
for x in ('/sbin', '/usr/sbin', '/usr/local/sbin'):
    if x not in pathlist:
        pathlist.append(x)
os.environ['PATH'] = os.pathsep.join(pathlist)


def tool_required(command):
    """
    Decorator that checks if the specified tool is installed
    """
    if not hasattr(tool_required, 'all'):
        tool_required.all = set()
    tool_required.all.add(command)
    def wrapper(original_function):
        if find_executable(command):
            @functools.wraps(original_function)
            def tool_check(*args, **kwargs):
                with profile('command', command):
                    return original_function(*args, **kwargs)
        else:
            @functools.wraps(original_function)
            def tool_check(*args, **kwargs):
                from .exc import RequiredToolNotFound
                raise RequiredToolNotFound(command)
        return tool_check
    return wrapper

def get_current_os():
    system = platform.system()
    if system == "Linux":
        # FIXME: Will break under Python 3.7, see:
        # https://docs.python.org/3/library/platform.html#platform.linux_distribution
        return platform.linux_distribution()[0]
    return system  # noqa
