# -*- coding: utf-8 -*-
#
# diffoscope: in-depth comparison of files, archives, and directories
#
# Copyright © 2016, 2017 Chris Lamb <lamby@debian.org>
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

import collections
import functools
import platform

try:
    import distro
except ImportError:
    distro = None

from distutils.spawn import find_executable

from .profiling import profile
from .external_tools import EXTERNAL_TOOLS, REMAPPED_TOOL_NAMES, GNU_TOOL_NAMES

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


def get_tool_name(tool):
    return REMAPPED_TOOL_NAMES.get(tool, tool)

def tool_prepend_prefix(prefix, *tools):
    if not prefix:
        return
    for tool in tools:
        REMAPPED_TOOL_NAMES[tool] = prefix + tool

def tool_required(command):
    """
    Decorator that checks if the specified tool is installed
    """
    from .exc import RequiredToolNotFound

    if not hasattr(tool_required, 'all'):
        tool_required.all = set()
    tool_required.all.add(command)

    def wrapper(fn):
        @functools.wraps(fn)
        def tool_check(*args, **kwargs):
            """
            Due to the way decorators are executed at import-time we defer the
            execution of `find_executable` until we actually run the decorated
            function (instead of prematurely returning a different version of
            `tool_check`).

            This ensures that any os.environ['PATH'] modifications are
            performed prior to the `find_executable` tests.
            """
            if command == get_tool_name(command) and not os_is_gnu() and tool_is_gnu(command):
                # try "g" + command for each tool, if we're on a non-GNU system
                if find_executable("g" + command):
                    tool_prepend_prefix("g", command)

            if not find_executable(get_tool_name(command)):
                raise RequiredToolNotFound(command)

            with profile('command', command):
                return fn(*args, **kwargs)
        return tool_check
    return wrapper

def tool_is_gnu(command):
    return command in GNU_TOOL_NAMES

def os_is_gnu():
    system = platform.system()
    return system in ("Linux", "GNU") or system.startswith("GNU/")

def get_current_os():
    system = platform.system()
    if system == "Linux":
        if distro:
            return distro.id()
    return system  # noqa

def get_current_distro_like():
    if distro:
        return distro.like().split()
    else:
        return []

def get_package_provider(tool, os=None):
    try:
        providers = EXTERNAL_TOOLS[tool]
    except KeyError:  # noqa
        return None

    try:
        return providers[get_current_os()]
    except KeyError:
        # lookup failed, try to look for a package for a similar distro
        for d in get_current_distro_like():
            try:
                return providers[d]
            except KeyError:
                pass

    return None
