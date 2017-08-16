# -*- coding: utf-8 -*-
#
# diffoscope: in-depth comparison of files, archives, and directories
#
# Copyright © 2014-2015 Jérémy Bobbio <lunar@debian.org>
#             2016      Chris Lamb <lamby@debian.org>
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

from .tools import get_tool_name, get_package_provider


class OutputParsingError(Exception):
    def __init__(self, command, object):
        self.command = command
        self.object_class = object.__class__

class RequiredToolNotFound(Exception):
    def __init__(self, command):
        self.command = get_tool_name(command)

    def get_package(self):
        return get_package_provider(self.command)

class ContainerExtractionError(Exception):
    def __init__(self, pathname, wrapped_exc):
        self.pathname = pathname
        self.wrapped_exc = wrapped_exc
