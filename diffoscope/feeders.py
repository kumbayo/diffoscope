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

from .config import Config
from .profiling import profile

logger = logging.getLogger(__name__)

DIFF_CHUNK = 4096


def from_raw_reader(in_file, filter=lambda buf: buf):
    def feeder(out_file):
        max_lines = Config().max_diff_input_lines
        end_nl = False
        line_count = 0

        # If we have a maximum size, hash the content as we go along so we can
        # display a nicer message.
        h = None
        if max_lines < float('inf'):
            h = hashlib.sha1()

        for buf in in_file:
            line_count += 1
            out = filter(buf)

            if h is not None:
                h.update(out)

            if line_count < max_lines:
                out_file.write(out)
            end_nl = buf[-1] == '\n'

        if h is not None and line_count >= max_lines:
            out_file.write("[ Too much input for diff (SHA1: {}) ]\n".format(
                h.hexdigest(),
            ).encode('utf-8'))
            end_nl = True

        return end_nl
    return feeder


def from_text_reader(in_file, filter=lambda text_buf: text_buf):
    def encoding_filter(text_buf):
        return filter(text_buf).encode('utf-8')
    return from_raw_reader(in_file, encoding_filter)


def from_command(command):
    def feeder(out_file):
        with profile('command', command.cmdline()[0]):
            feeder = from_raw_reader(
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


def from_text(content):
    def feeder(f):
        for offset in range(0, len(content), DIFF_CHUNK):
            f.write(content[offset:offset + DIFF_CHUNK].encode('utf-8'))
        return content and content[-1] == '\n'
    return feeder


def empty():
    def feeder(f):
        return False
    return feeder
