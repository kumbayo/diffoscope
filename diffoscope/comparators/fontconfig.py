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

import re
import struct

from diffoscope.difference import Difference

from .utils.file import File
from .utils.command import Command


class FontconfigCacheFile(File):
    MAGIC = struct.pack('<H', 0xFC04)
    RE_FILE_EXTENSION = re.compile(r'\-le64\.cache-4$')

    @staticmethod
    def recognizes(file):
        if not FontconfigCacheFile.RE_FILE_EXTENSION.search(file.name):
            return False

        with open(file.path, 'rb') as f:
            return f.read(len(FontconfigCacheFile.MAGIC)) == \
                FontconfigCacheFile.MAGIC

    def compare_details(self, other, source=None):
        return [Difference.from_text(
            describe_cache_file(self.path),
            describe_cache_file(other.path),
            self.path,
            other.path,
        )]


def describe_cache_file(filename):
    fmt = '<IIQQQQQQQ'
    fields = (
        'magic', 'version', 'size', 'dir', 'dirs', 'dirs_count', 'set',
        'checksum', 'checksum_nano',
    )

    with open(filename, 'rb') as f:
        data = struct.unpack(fmt, f.read(struct.calcsize(fmt)))
        kwargs = {x: y for x, y in zip(fields, data)}

        kwargs['dir_name'] = read_null_terminated_string(f, kwargs['dir'])

    return """
struct FcCache {{
    unsigned int    magic = 0x{magic:08X};  /* FC_CACHE_MAGIC_MMAP or FC_CACHE_ALLOC */
    int             version = {version};  /* FC_CACHE_VERSION_NUMBER */
    intptr_t        size = {size};  /* size of file */
    intptr_t        dir = 0x{dir};  /* offset to dir name ("{dir_name}") */
    intptr_t        dirs = 0x{dirs:08X};  /* offset to subdirs */
    int             dirs_count = {dirs_count};  /* number of subdir strings */
    intptr_t        set = 0x{set:08X};  /* offset to font set */
    int             checksum = {checksum};  /* checksum of directory state */
    int64_t         checksum_nano = {checksum_nano};  /* checksum of directory state */
}};
""".format(**kwargs)


def read_null_terminated_string(fileobj, offset=None):
    result = ''

    if offset is not None:
        fileobj.seek(offset)

    while True:
        x = fileobj.read(1).decode('ascii')
        if x in ('', '\0'):
            break
        result += x

    return result
