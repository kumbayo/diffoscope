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

import signal
import hashlib
import logging
import subprocess

from .exc import RequiredToolNotFound
from .diff import diff, reverse_unified_diff
from .config import Config
from .excludes import command_excluded
from .profiling import profile

DIFF_CHUNK = 4096

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
            self._size_cache = (len(self.unified_diff) +
                len(self.source1) +
                len(self.source2) +
                sum(map(len, self.comments)) +
                sum(d.size() for d in self._details) +
                sum(v.size() for v in self._visuals))
        return self._size_cache

    def has_children(self):
        """
        Whether there are children.

        Useful for e.g. choosing whether to display [+]/[-] controls.
        """

        return self._unified_diff is not None or self._details or self._visuals

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
            make_feeder_from_text(content1),
            make_feeder_from_text(content2),
            *args,
            **kwargs
        )

    @staticmethod
    def from_raw_readers(file1, file2, *args, **kwargs):
        return Difference.from_feeder(
            make_feeder_from_raw_reader(file1),
            make_feeder_from_raw_reader(file2),
            *args,
            **kwargs
        )

    @staticmethod
    def from_text_readers(file1, file2, *args, **kwargs):
        return Difference.from_feeder(
            make_feeder_from_text_reader(file1),
            make_feeder_from_text_reader(file2),
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
                feeder = empty_file_feeder()
            else:
                command = klass(path, *command_args)
                feeder = make_feeder_from_command(command)
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


def make_feeder_from_text_reader(in_file, filter=lambda text_buf: text_buf):
    def encoding_filter(text_buf):
        return filter(text_buf).encode('utf-8')
    return make_feeder_from_raw_reader(in_file, encoding_filter)


def make_feeder_from_command(command):
    def feeder(out_file):
        with profile('command', command.cmdline()[0]):
            feeder = make_feeder_from_raw_reader(
                command.stdout,
                command.filter,
            )
            end_nl = feeder(out_file)
            if command.poll() is None:
                command.terminate()
            returncode = command.wait()
        if returncode not in (0, -signal.SIGTERM):
            raise subprocess.CalledProcessError(
                returncode,
                command.cmdline(),
                output=command.stderr.getvalue(),
            )
        return end_nl
    return feeder


def make_feeder_from_raw_reader(in_file, filter=lambda buf: buf):
    def feeder(out_file):
        max_lines = Config().max_diff_input_lines
        line_count = 0
        end_nl = False
        h = None
        if max_lines < float('inf'):
            h = hashlib.sha1()
        for buf in in_file:
            line_count += 1
            out = filter(buf)
            if h:
                h.update(out)
            if line_count < max_lines:
                out_file.write(out)
            end_nl = buf[-1] == '\n'
        if h and line_count >= max_lines:
            out_file.write("[ Too much input for diff (SHA1: {}) ]\n".format(
                h.hexdigest(),
            ).encode('utf-8'))
            end_nl = True
        return end_nl
    return feeder


def make_feeder_from_text(content):
    def feeder(f):
        for offset in range(0, len(content), DIFF_CHUNK):
            f.write(content[offset:offset + DIFF_CHUNK].encode('utf-8'))
        return content and content[-1] == '\n'
    return feeder


def empty_file_feeder():
    def feeder(f):
        return False
    return feeder
