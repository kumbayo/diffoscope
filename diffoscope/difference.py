# -*- coding: utf-8 -*-
#
# diffoscope: in-depth comparison of files, archives, and directories
#
# Copyright © 2014-2015 Jérémy Bobbio <lunar@debian.org>
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

import heapq
import logging

from . import feeders
from .exc import RequiredToolNotFound
from .diff import diff, reverse_unified_diff
from .excludes import command_excluded

logger = logging.getLogger(__name__)


class Difference(object):
    def __init__(self, unified_diff, path1, path2, source=None, comment=None, has_internal_linenos=False, details=None):
        self._unified_diff = unified_diff

        self._comments = []
        if comment:
            if type(comment) is list:
                self._comments.extend(comment)
            else:
                self._comments.append(comment)

        # Allow to override declared file paths, useful when comparing
        # tempfiles
        if source:
            if type(source) is list:
                self._source1, self._source2 = source
            else:
                self._source1 = source
                self._source2 = source
        else:
            self._source1 = path1
            self._source2 = path2

        # Ensure renderable types
        if not isinstance(self._source1, str):
            raise TypeError("path1/source[0] is not a string")
        if not isinstance(self._source2, str):
            raise TypeError("path2/source[1] is not a string")

        # Whether the unified_diff already contains line numbers inside itself
        self._has_internal_linenos = has_internal_linenos
        self._details = details or []
        self._visuals = []
        self._size_cache = None

    def __repr__(self):
        return "<Difference %s -- %s %s>" % (
            self._source1,
            self._source2,
            self._details,
        )

    def get_reverse(self):
        logger.debug("Reverse orig %s %s", self.source1, self.source2)

        if self._visuals:
            raise NotImplementedError(
                "Reversing VisualDifference is not yet implemented",
            )

        diff = self.unified_diff
        if diff is not None:
            diff = reverse_unified_diff(self.unified_diff)

        return Difference(
            diff,
            self.source2,
            self.source1,
            comment=self.comments,
            has_internal_linenos=self.has_internal_linenos,
            details=[d.get_reverse() for d in self._details],
        )

    def equals(self, other):
        return self == other or (
            self.unified_diff == other.unified_diff and
            self.source1 == other.source1 and
            self.source2 == other.source2 and
            self.comments == other.comments and
            self.has_internal_linenos == other.has_internal_linenos and
            all(x.equals(y) for x, y in zip(self.details, other.details)))

    def size(self):
        if self._size_cache is None:
            self._size_cache = sum(d.size_self() for d in self.traverse_depth())
        return self._size_cache

    def size_self(self):
        """Size, excluding children."""
        return ((len(self.unified_diff) if self.unified_diff else 0) +
                (len(self.source1) if self.source1 else 0) +
                (len(self.source2) if self.source2 else 0) +
                sum(map(len, self.comments)) +
                sum(v.size() for v in self._visuals))

    def has_visible_children(self):
        """
        Whether there are visible children.

        Useful for e.g. choosing whether to display [+]/[-] controls.
        """
        return (self._unified_diff is not None or
                self._comments or self._details or self._visuals)

    def traverse_depth(self, depth=-1):
        yield self
        if depth != 0:
            for d in self._details:
                yield from d.traverse_depth(depth-1)

    def traverse_breadth(self, queue=None):
        queue = queue if queue is not None else [self]
        if queue:
            top = queue.pop(0)
            yield top
            queue.extend(top._details)
            yield from self.traverse_breadth(queue)

    def traverse_heapq(self, scorer, queue=None):
        """Traverse the difference tree using a priority queue, where each node
        is scored according to a user-supplied function, and nodes with smaller
        scores are traversed first (after they have been added to the queue).

        The function `scorer` takes two arguments, a node to score and the
        score of its parent node (or None if there is no parent). It should
        return the score of the input node.
        """
        queue = queue if queue is not None else [(scorer(self, None), self)]
        if queue:
            val, top = heapq.heappop(queue)
            yield top
            for d in top._details:
                heapq.heappush(queue, (scorer(d, val), d))
            yield from self.traverse_heapq(scorer, queue)

    @staticmethod
    def from_feeder(feeder1, feeder2, path1, path2, source=None, comment=None, **kwargs):
        try:
            unified_diff = diff(feeder1, feeder2)
            if not unified_diff:
                return None
            return Difference(
                unified_diff,
                path1,
                path2,
                source,
                comment,
                **kwargs
            )
        except RequiredToolNotFound:
            difference = Difference(None, path1, path2, source)
            difference.add_comment("diff is not available")
            if comment:
                difference.add_comment(comment)
            return difference

    @staticmethod
    def from_text(content1, content2, *args, **kwargs):
        return Difference.from_feeder(
            feeders.from_text(content1),
            feeders.from_text(content2),
            *args,
            **kwargs
        )

    @staticmethod
    def from_raw_readers(file1, file2, *args, **kwargs):
        return Difference.from_feeder(
            feeders.from_raw_reader(file1),
            feeders.from_raw_reader(file2),
            *args,
            **kwargs
        )

    @staticmethod
    def from_text_readers(file1, file2, *args, **kwargs):
        return Difference.from_feeder(
            feeders.from_text_reader(file1),
            feeders.from_text_reader(file2),
            *args,
            **kwargs
        )

    @staticmethod
    def from_command(klass, path1, path2, *args, **kwargs):
        command_args = []
        if 'command_args' in kwargs:
            command_args = kwargs['command_args']
            del kwargs['command_args']

        def command_and_feeder(path):
            command = None
            if path == '/dev/null':
                feeder = feeders.empty()
            else:
                command = klass(path, *command_args)
                feeder = feeders.from_command(command)
                if command_excluded(command.shell_cmdline()):
                    return None, None
                command.start()
            return feeder, command

        feeder1, command1 = command_and_feeder(path1)
        feeder2, command2 = command_and_feeder(path2)
        if not feeder1 or not feeder2:
            return None

        if 'source' not in kwargs:
            source_cmd = command1 or command2
            kwargs['source'] = source_cmd.shell_cmdline()

        difference = Difference.from_feeder(
            feeder1,
            feeder2,
            path1,
            path2,
            *args,
            **kwargs
        )
        if not difference:
            return None

        if command1 and command1.stderr_content:
            difference.add_comment("stderr from `{}`:".format(
                ' '.join(command1.cmdline()),
            ))
            difference.add_comment(command1.stderr_content)
        if command2 and command2.stderr_content:
            difference.add_comment("stderr from `{}`:".format(
                ' '.join(command2.cmdline()),
            ))
            difference.add_comment(command2.stderr_content)

        return difference

    @property
    def comment(self):
        return '\n'.join(self._comments)

    @property
    def comments(self):
        return self._comments

    def add_comment(self, comment):
        for line in comment.splitlines():
            self._comments.append(line)
        self._size_cache = None

    @property
    def source1(self):
        return self._source1

    @property
    def source2(self):
        return self._source2

    @property
    def unified_diff(self):
        return self._unified_diff

    @property
    def has_internal_linenos(self):
        return self._has_internal_linenos

    @property
    def details(self):
        return self._details

    @property
    def visuals(self):
        return self._visuals

    def add_details(self, differences):
        if len([d for d in differences if type(d) is not Difference]) > 0:
            raise TypeError("'differences' must contains Difference objects'")
        self._details.extend(differences)
        self._size_cache = None

    def add_visuals(self, visuals):
        if any([type(v) is not VisualDifference for v in visuals]):
            raise TypeError("'visuals' must contain VisualDifference objects'")
        self._visuals.extend(visuals)
        self._size_cache = None


class VisualDifference(object):
    def __init__(self, data_type, content, source):
        self._data_type = data_type
        self._content = content
        self._source = source

    @property
    def data_type(self):
        return self._data_type

    @property
    def content(self):
        return self._content

    @property
    def source(self):
        return self._source

    def size(self):
        return len(self.data_type) + len(self.content) + len(self.source)
