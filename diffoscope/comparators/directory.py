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

import os
import re
import logging
import subprocess
import collections
import itertools

from diffoscope.exc import RequiredToolNotFound
from diffoscope.tools import tool_required
from diffoscope.config import Config
from diffoscope.progress import Progress
from diffoscope.difference import Difference

from .binary import FilesystemFile
from .utils.command import Command
from .utils.container import Container

logger = logging.getLogger(__name__)


def list_files(path):
    path = os.path.realpath(path)
    all_files = []
    for root, dirs, names in os.walk(path):
        all_files.extend([os.path.join(root[len(path) + 1:], dir) for dir in dirs])
        all_files.extend([os.path.join(root[len(path) + 1:], name) for name in names])
    all_files.sort()
    return all_files


if os.uname()[0] == 'FreeBSD':
    class Stat(Command):
        @tool_required('stat')
        def cmdline(self):
            return [
                'stat',
                '-t', '%Y-%m-%d %H:%M:%S',
                '-f', '%Sp %l %Su %Sg %z %Sm %k %b %#Xf',
                self.path,
            ]
else:
    class Stat(Command):
        @tool_required('stat')
        def cmdline(self):
            return ['stat', self.path]

        FILE_RE = re.compile(r'^\s*File:.*$')
        DEVICE_RE = re.compile(r'Device: [0-9a-f]+h/[0-9]+d\s+')
        INODE_RE = re.compile(r'Inode: [0-9]+\s+')
        ACCESS_TIME_RE = re.compile(r'^Access: [0-9]{4}-[0-9]{2}-[0-9]{2}.*$')
        CHANGE_TIME_RE = re.compile(r'^Change: [0-9]{4}-[0-9]{2}-[0-9]{2}.*$')

        def filter(self, line):
            line = line.decode('utf-8')
            line = Stat.FILE_RE.sub('', line)
            line = Stat.DEVICE_RE.sub('', line)
            line = Stat.INODE_RE.sub('', line)
            line = Stat.ACCESS_TIME_RE.sub('', line)
            line = Stat.CHANGE_TIME_RE.sub('', line)
            return line.encode('utf-8')


@tool_required('lsattr')
def lsattr(path):
    """
    NB. Difficult to replace with in-Python version. See
    <https://stackoverflow.com/questions/35501249/python-get-linux-file-immutable-attribute/38092961#38092961>
    """

    try:
        output = subprocess.check_output(
            ['lsattr', '-d', path],
            shell=False,
            stderr=subprocess.STDOUT,
        ).decode('utf-8')
        return output.split()[0]
    except subprocess.CalledProcessError as e:
        if e.returncode == 1:
            # filesystem doesn't support xattrs
            return ''


class Getfacl(Command):
    @tool_required('getfacl')
    def cmdline(self):
        osname = os.uname()[0]
        if osname == 'FreeBSD':
            return ['getfacl', '-q', '-h', self.path]
        return ['getfacl', '-p', '-c', self.path]


def compare_meta(path1, path2):
    if Config().exclude_directory_metadata:
        logger.debug("Excluding directory metadata for paths (%s, %s)", path1, path2)
        return []

    logger.debug('compare_meta(%s, %s)', path1, path2)
    differences = []

    try:
        differences.append(Difference.from_command(Stat, path1, path2))
    except RequiredToolNotFound:
        logger.error("Unable to find 'stat'! Is PATH wrong?")
    if os.path.islink(path1) or os.path.islink(path2):
        return [d for d in differences if d is not None]
    try:
        differences.append(Difference.from_command(Getfacl, path1, path2))
    except RequiredToolNotFound:
        logger.warning("Unable to find 'getfacl', some directory metadata differences might not be noticed.")
    try:
        lsattr1 = lsattr(path1)
        lsattr2 = lsattr(path2)
        differences.append(Difference.from_text(
            lsattr1,
            lsattr2,
            path1,
            path2,
            source='lsattr',
        ))
    except RequiredToolNotFound:
        logger.info("Unable to find 'lsattr', some directory metadata differences might not be noticed.")
    return [d for d in differences if d is not None]


def compare_directories(path1, path2, source=None):
    return FilesystemDirectory(path1).compare(FilesystemDirectory(path2))


class Directory(object):
    @staticmethod
    def recognizes(file):
        return file.is_directory()


class FilesystemDirectory(Directory):
    def __init__(self, path):
        self._path = path

    @property
    def path(self):
        return self._path

    @property
    def name(self):
        return self._path

    @property
    def as_container(self):
        if not hasattr(self, '_as_container'):
            self._as_container = DirectoryContainer(self)
        return self._as_container

    def is_directory(self):
        return True

    def has_same_content_as(self, other):
        # no shortcut
        return False

    def compare(self, other, source=None):
        differences = []

        listing_diff = Difference.from_text(
            '\n'.join(list_files(self.path)),
            '\n'.join(list_files(other.path)),
            self.path,
            other.path,
            source='file list',
        )
        if listing_diff:
            differences.append(listing_diff)

        differences.extend(compare_meta(self.name, other.name))

        my_container = DirectoryContainer(self)
        other_container = DirectoryContainer(other)
        differences.extend(my_container.compare(other_container))

        if not differences:
            return None

        difference = Difference(None, self.path, other.path, source)
        difference.add_details(differences)
        return difference


class DirectoryContainer(Container):
    def get_member_names(self):
        return sorted(os.listdir(self.source.path or '.'))

    def get_member(self, member_name):
        member_path = os.path.join(self.source.path, member_name)

        if not os.path.islink(member_path) and os.path.isdir(member_path):
            return FilesystemDirectory(member_path)

        return FilesystemFile(
            os.path.join(self.source.path, member_name),
            container=self,
        )

    def comparisons(self, other):
        my_members = collections.OrderedDict(self.get_adjusted_members_sizes())
        other_members = collections.OrderedDict(other.get_adjusted_members_sizes())
        total_size = sum(x[1] for x in my_members.values()) + sum(x[1] for x in other_members.values())

        to_compare = set(my_members.keys()).intersection(other_members.keys())
        with Progress(total_size) as p:
            for name in sorted(to_compare):
                my_file, my_size = my_members[name]
                other_file, other_size = other_members[name]
                p.begin_step(my_size + other_size, msg=name)
                yield my_file, other_file, name

    def compare(self, other, source=None):
        from .utils.compare import compare_files

        def compare_pair(file1, file2, source):
            inner_difference = compare_files(file1, file2, source=source)
            meta_differences = compare_meta(file1.name, file2.name)
            if meta_differences and not inner_difference:
                inner_difference = Difference(None, file1.path, file2.path)
            if inner_difference:
                inner_difference.add_details(meta_differences)
            return inner_difference

        return filter(
            None,
            itertools.starmap(compare_pair, self.comparisons(other)),
        )
