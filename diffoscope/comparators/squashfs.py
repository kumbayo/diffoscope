# -*- coding: utf-8 -*-
#
# diffoscope: in-depth comparison of files, archives, and directories
#
# Copyright © 2015 Reiner Herrmann <reiner@reiner-h.de>
#             2015 Jérémy Bobbio <lunar@debian.org>
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
import re
import stat
import logging
import functools
import subprocess
import collections

from diffoscope.tools import tool_required
from diffoscope.difference import Difference
from diffoscope.tempfiles import get_temporary_directory

from .utils.file import File
from .device import Device
from .symlink import Symlink
from .directory import Directory
from .utils.archive import Archive, ArchiveMember
from .utils.command import Command

logger = logging.getLogger(__name__)


class SquashfsSuperblock(Command):
    @tool_required('unsquashfs')
    def cmdline(self):
        return ['unsquashfs', '-s', self.path]

    def filter(self, line):
        # strip filename
        return re.sub(
            r'^(Found a valid .*) on .*',
            '\\1',
            line.decode('utf-8'),
        ).encode('utf-8')


class SquashfsListing(Command):
    @tool_required('unsquashfs')
    def cmdline(self):
        return ['unsquashfs', '-d', '', '-lls', self.path]


class SquashfsInvalidLineFormat(Exception):
    pass


class SquashfsMember(ArchiveMember):
    def is_directory(self):
        return False

    def is_symlink(self):
        return False

    def is_device(self):
        return False

    @property
    def path(self):
        # Use our extracted version and also avoid creating a temporary
        # directory per-file in ArchiveMember.path.
        return os.path.join(self.container._temp_dir, self._name)

    @property
    def name(self):
        # Don't include the leading "." in the output  (eg. "./etc/shadow")
        return self._name[1:]


class SquashfsRegularFile(SquashfsMember):
    # Example line:
    # -rw-r--r-- user/group   446 2015-06-24 14:49 squashfs-root/text
    LINE_RE = re.compile(r'^\S+\s+\S+\s+\S+\s+\S+\s+\S+\s+(?P<member_name>.*)$')

    @staticmethod
    def parse(line):
        m = SquashfsRegularFile.LINE_RE.match(line)
        if not m:
            raise SquashfsInvalidLineFormat("invalid line format")
        return m.groupdict()

    def __init__(self, archive, member_name):
        SquashfsMember.__init__(self, archive, member_name)


class SquashfsDirectory(Directory, SquashfsMember):
    # Example line:
    # drwxr-xr-x user/group    51 2015-06-24 14:47 squashfs-root
    LINE_RE = re.compile(r'^\S+\s+\S+\s+\S+\s+\S+\s+\S+\s+(?P<member_name>.*)$')

    @staticmethod
    def parse(line):
        m = SquashfsDirectory.LINE_RE.match(line)
        if not m:
            raise SquashfsInvalidLineFormat("invalid line format")
        return m.groupdict()

    def __init__(self, archive, member_name):
        SquashfsMember.__init__(self, archive, member_name or '/')

    def compare(self, other, source=None):
        return None

    def has_same_content_as(self, other):
        return False

    @property
    def path(self):
        raise NotImplementedError("SquashfsDirectory is not meant to be extracted.")

    def is_directory(self):
        return True

    def get_member_names(self):
        raise ValueError("squashfs are compared as a whole.")  # noqa

    def get_member(self, member_name):
        raise ValueError("squashfs are compared as a whole.")  # noqa


class SquashfsSymlink(Symlink, SquashfsMember):
    # Example line:
    # lrwxrwxrwx user/group   6 2015-06-24 14:47 squashfs-root/link -> broken
    LINE_RE = re.compile(
        r'^\S+\s+\S+\s+\S+\s+\S+\s+\S+\s+(?P<member_name>.*)\s+->\s+(?P<destination>.*)$',
    )

    @staticmethod
    def parse(line):
        m = SquashfsSymlink.LINE_RE.match(line)
        if not m:
            raise SquashfsInvalidLineFormat("invalid line format")
        return m.groupdict()

    def __init__(self, archive, member_name, destination):
        SquashfsMember.__init__(self, archive, member_name)
        self._destination = destination

    def is_symlink(self):
        return True

    @property
    def symlink_destination(self):
        return self._destination


class SquashfsDevice(Device, SquashfsMember):
    # Example line:
    # crw-r--r-- root/root  1,  3 2015-06-24 14:47 squashfs-root/null
    LINE_RE = re.compile(
        r'^(?P<kind>c|b)\S+\s+\S+\s+(?P<major>\d+),\s*(?P<minor>\d+)\s+\S+\s+\S+\s+(?P<member_name>.*)$',
    )

    KIND_MAP = {
        'c': stat.S_IFCHR,
        'b': stat.S_IFBLK,
    }

    @staticmethod
    def parse(line):
        m = SquashfsDevice.LINE_RE.match(line)
        if not m:
            raise SquashfsInvalidLineFormat("invalid line format")

        d = m.groupdict()
        try:
            d['mode'] = SquashfsDevice.KIND_MAP[d['kind']]
            del d['kind']
        except KeyError:
            raise SquashfsInvalidLineFormat("unknown device kind %s" % d['kind'])

        try:
            d['major'] = int(d['major'])
        except ValueError:
            raise SquashfsInvalidLineFormat(
                "unable to parse major number %s" % d['major'],
            )

        try:
            d['minor'] = int(d['minor'])
        except ValueError:
            raise SquashfsInvalidLineFormat(
                "unable to parse minor number %s" % d['minor'],
            )
        return d

    def __init__(self, archive, member_name, mode, major, minor):
        SquashfsMember.__init__(self, archive, member_name)
        self._mode = mode
        self._major = major
        self._minor = minor

    def get_device(self):
        return (self._mode, self._major, self._minor)

    def is_device(self):
        return True


class SquashfsContainer(Archive):
    MEMBER_CLASS = {
        'd': SquashfsDirectory,
        'l': SquashfsSymlink,
        'c': SquashfsDevice,
        'b': SquashfsDevice,
        '-': SquashfsRegularFile
    }

    def open_archive(self):
        return True

    def close_archive(self):
        pass

    def get_member(self, member_name):
        self.ensure_unpacked()
        cls, kwargs = self._members[member_name]
        return cls(self, member_name, **kwargs)

    def extract(self, member_name, destdir):
        # Ignore destdir argument and use our unpacked path
        self.ensure_unpacked()
        return member_name

    def get_member_names(self):
        self.ensure_unpacked()
        return self._members.keys()

    def ensure_unpacked(self):
        if hasattr(self, '_members'):
            return

        self._members = collections.OrderedDict()
        self._temp_dir = get_temporary_directory().name

        logger.debug("Extracting %s to %s", self.source.path, self._temp_dir)

        output = subprocess.check_output((
            'unsquashfs',
            '-n',
            '-f',
            '-no',
            '-li',
            '-d', '.',
            self.source.path,
        ), stderr=subprocess.PIPE, cwd=self._temp_dir)

        output = iter(output.decode('utf-8').rstrip('\n').split('\n'))

        # Skip headers
        for _ in iter(functools.partial(next, output), ''):
            pass

        for line in output:
            if not line:
                continue

            try:
                cls = self.MEMBER_CLASS[line[0]]
            except KeyError:
                logger.debug("Unknown squashfs entry: %s", line)
                continue

            try:
                kwargs = cls.parse(line)
            except SquashfsInvalidLineFormat:
                continue

            # Pop to avoid duplicating member name in the key and the value
            member_name = kwargs.pop('member_name')

            self._members[member_name] = (cls, kwargs)

        logger.debug(
            "Extracted %d entries from %s to %s",
            len(self._members), self.source.path, self._temp_dir,
        )


class SquashfsFile(File):
    CONTAINER_CLASS = SquashfsContainer
    RE_FILE_TYPE = re.compile(r'^Squashfs filesystem\b')

    def compare_details(self, other, source=None):
        return [
            Difference.from_command(SquashfsSuperblock, self.path, other.path),
            Difference.from_command(SquashfsListing, self.path, other.path),
        ]
