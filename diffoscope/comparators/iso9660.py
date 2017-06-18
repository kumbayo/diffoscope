# -*- coding: utf-8 -*-
#
# diffoscope: in-depth comparison of files, archives, and directories
#
# Copyright © 2015 Jérémy Bobbio <lunar@debian.org>
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

import re
import subprocess

from diffoscope.tools import tool_required
from diffoscope.difference import Difference

from .utils.file import File
from .utils.command import Command
from .utils.libarchive import LibarchiveContainer


@tool_required('isoinfo')
def get_iso9660_names(path):
    return subprocess.check_output((
        'isoinfo',
        '-R',  # Always use RockRidge for names
        '-f',
        '-i',
        path,
    ), shell=False).strip().split('\n')


class ISO9660PVD(Command):
    @tool_required('isoinfo')
    def cmdline(self):
        return ['isoinfo', '-d', '-i', self.path]


class ISO9660Listing(Command):
    def __init__(self, path, extension=None, *args, **kwargs):
        self._extension = extension
        super().__init__(path, *args, **kwargs)

    @tool_required('isoinfo')
    def cmdline(self):
        cmd = ['isoinfo', '-l', '-i', self.path]

        if self._extension == 'joliet':
            cmd.extend(['-J', '-j', 'iso8859-15'])
        elif self._extension == 'rockridge':
            cmd.extend(['-R'])

        return cmd

    def filter(self, line):
        if self._extension == 'joliet':
            return line.decode('iso-8859-15').encode('utf-8')
        return line


class Iso9660File(File):
    CONTAINER_CLASS = LibarchiveContainer
    RE_FILE_TYPE = re.compile(r'\bISO 9660\b')

    @classmethod
    def recognizes(cls, file):
        if file.magic_file_type and \
                cls.RE_FILE_TYPE.search(file.magic_file_type):
            return True

        # Sometimes CDs put things like MBRs at the front which is an expected
        # part of the ISO9660 standard, but file(1)/libmagic doesn't detect
        # this. <https://en.wikipedia.org/wiki/ISO_9660#Specifications>.
        with open(file.path, 'rb') as f:
            f.seek(32769)
            return f.read(5) == b'CD001'

        return False

    def compare_details(self, other, source=None):
        differences = []

        for klass in (ISO9660PVD, ISO9660Listing):
            differences.append(Difference.from_command(
                klass, self.path, other.path,
            ))

        for x in ('joliet', 'rockridge'):
            try:
                differences.append(Difference.from_command(
                    ISO9660Listing, self.path, other.path, command_args=(x,),
                ))
            except subprocess.CalledProcessError:
                # Probably no joliet or rockridge data
                pass

        return differences
