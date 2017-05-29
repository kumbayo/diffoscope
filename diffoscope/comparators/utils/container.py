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

import abc
import logging
import itertools
from collections import OrderedDict

from diffoscope.config import Config
from diffoscope.difference import Difference
from diffoscope.excludes import filter_excludes
from diffoscope.progress import Progress

from ..missing_file import MissingFile

from .file import path_apparent_size
from .fuzzy import perform_fuzzy_matching

NO_COMMENT = None

logger = logging.getLogger(__name__)


class Container(object, metaclass=abc.ABCMeta):
    def __new__(cls, source):
        if isinstance(source, MissingFile):
            new = super(Container, MissingContainer).__new__(MissingContainer)
            new.__init__(source)
            return new

        return super(Container, cls).__new__(cls)

    def __init__(self, source):
        self._source = source

        # Keep a count of how "nested" we are
        self.depth = 0
        if hasattr(source, 'container') and source.container is not None:
            self.depth = source.container.depth + 1

    @property
    def source(self):
        return self._source

    @abc.abstractmethod
    def get_member_names(self):
        raise NotImplementedError()

    @abc.abstractmethod
    def get_member(self, member_name):
        raise NotImplementedError()

    def get_filtered_members(self):
        # If your get_member implementation is O(n) then this will be O(n^2)
        # cost. In such cases it is HIGHLY RECOMMENDED to override this as well
        for name in filter_excludes(self.get_member_names()):
            yield name, self.get_member(name)

    def get_adjusted_members(self):
        """
        Returns an iterable of pairs. The key is what is used to match when
        comparing containers. This may be used to e.g. strip off version
        numbers, hashes, etc, efficiently for known file formats, so that we
        don't need to use the expensive tlsh "fuzzy-hashing" logic.

        Note that containers with 1 element are already force-compared against
        other containers with 1 element, so you don't need to override this
        method for those cases.
        """
        return self.get_filtered_members()

    def lookup_file(self, *names):
        """
        Try to fetch a specific file by digging in containers.
        """

        from .specialize import specialize

        name, remainings = names[0], names[1:]
        try:
            file = self.get_member(name)
        except KeyError:
            return None

        logger.debug("lookup_file(%s) -> %s", names, file)
        specialize(file)
        if not remainings:
            return file

        container = file.as_container
        if not container:
            return None

        return container.lookup_file(*remainings)

    def get_adjusted_members_sizes(self):
        for name, member in self.get_adjusted_members():
            if member.is_directory():
                size = 4096 # default "size" of a directory
            else:
                size = path_apparent_size(member.path)
            yield name, (member, size)

    def comparisons(self, other):
        my_members = OrderedDict(self.get_adjusted_members_sizes())
        other_members = OrderedDict(other.get_adjusted_members_sizes())
        total_size = sum(x[1] for x in itertools.chain(my_members.values(), other_members.values()))
        # TODO: progress could be a bit more accurate here, give more weight to fuzzy-hashed files
        # TODO: merge DirectoryContainer.comparisons() into this

        with Progress(total_size) as p:
            def prep_yield(my_name, other_name, comment=NO_COMMENT):
                my_member, my_size = my_members.pop(my_name)
                other_member, other_size = other_members.pop(other_name)
                p.begin_step(my_size + other_size, msg=my_member.progress_name)
                return my_member, other_member, comment

            # if both containers contain 1 element, compare these
            if len(my_members) == 1 and len(other_members) == 1:
                yield prep_yield(next(iter(my_members.keys())),
                                 next(iter(other_members.keys())))
                return

            other_names = set(other_members.keys())
            # keep it sorted like my_members
            both_names = [name for name in my_members.keys() if name in other_names]
            for name in both_names:
                yield prep_yield(name, name)

            for my_name, other_name, score in perform_fuzzy_matching(my_members, other_members):
                comment = "Files similar despite different names" \
                    " (difference score: {})".format(score)
                yield prep_yield(my_name, other_name, comment)

            if Config().new_file:
                for my_member, my_size in my_members.values():
                    p.begin_step(my_size, msg=my_member.progress_name)
                    yield my_member, MissingFile('/dev/null', my_member), NO_COMMENT

                for other_member, other_size in other_members.values():
                    p.begin_step(other_size, msg=other_member.progress_name)
                    yield MissingFile('/dev/null', other_member), other_member, NO_COMMENT

    def compare(self, other, source=None, no_recurse=False):
        from .compare import compare_files

        def compare_pair(file1, file2, comment):
            difference = compare_files(file1, file2, source=None, diff_content_only=no_recurse)
            if comment:
                if difference is None:
                    difference = Difference(None, file1.name, file2.name)
                difference.add_comment(comment)
            return difference

        return filter(None, itertools.starmap(compare_pair, self.comparisons(other)))


class MissingContainer(Container):
    def get_member_names(self):
        return self.source.other_file.as_container.get_member_names()

    def get_member(self, member_name):
        return MissingFile('/dev/null')
