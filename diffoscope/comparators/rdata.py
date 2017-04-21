# -*- coding: utf-8 -*-
#
# diffoscope: in-depth comparison of files, archives, and directories
#
# Copyright © 2017 Ximin Luo <infinity0@debian.org>
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

from diffoscope.tools import tool_required
from diffoscope.difference import Difference

from .utils.file import File
from .utils.command import Command

import shutil
import os.path
import binascii


HEADER = binascii.a2b_hex("580a000000020003")

# has to be one line
DUMP_RDB = """lazyLoad(commandArgs(TRUE)); for (obj in ls()) { print(obj); for (line in deparse(get(obj))) cat(line,"\\n"); }"""
# unfortunately this above snippet can't detect the build-path differences so
# diffoscope still falls back to a hexdump


def check_rds_extension(f):
    return f.name.endswith(".rds") or f.name.endswith(".rdx")

def ensure_archive_rdx(f):
    if not f.container or f.path.endswith(".rdb"):
        return f.path

    # if we're in an archive, copy the .rdx file over so R can read it
    bname = os.path.basename(f.name)
    assert bname.endswith(".rdb")
    rdx_name = f.name[:-4] + ".rdx"
    try:
        rdx_path = f.container.get_member(rdx_name).path
    except KeyError:
        return f.path
        # R will fail, diffoscope will report the error and continue
    shutil.copy(f.path, f.path + ".rdb")
    shutil.copy(rdx_path, f.path + ".rdx")
    return f.path + ".rdb"

class RdsReader(Command):
    @tool_required('Rscript')
    def cmdline(self):
        return [
            'Rscript', '-e', 'args <- commandArgs(TRUE); readRDS(args[1])',
            self.path
        ]

class RdsFile(File):
    @staticmethod
    def recognizes(file):
        if check_rds_extension(file) or \
                file.container and \
                check_rds_extension(file.container.source):
            with open(file.path, 'rb') as f:
                return f.read(8) == HEADER
        return False

    def compare_details(self, other, source=None):
        return [Difference.from_command(RdsReader, self.path, other.path)]

class RdbReader(Command):
    @tool_required('Rscript')
    def cmdline(self):
        return ['Rscript', '-e', DUMP_RDB, self.path[:-4]]

class RdbFile(File):
    @staticmethod
    def recognizes(file):
        if file.name.endswith(".rdb"):
            return True

    def compare_details(self, other, source=None):
        self_path = ensure_archive_rdx(self)
        other_path = ensure_archive_rdx(other)
        return [Difference.from_command(RdbReader, self_path, other_path)]
