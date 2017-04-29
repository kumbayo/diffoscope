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

import re
import logging
import functools
import subprocess

from diffoscope.config import Config
from diffoscope.tools import tool_required
from diffoscope.difference import Difference

from .image import pixel_difference, flicker_difference, same_size
from .utils.file import File
from .utils.command import Command

logger = logging.getLogger(__name__)


class Sng(Command):
    @tool_required('sng')
    def cmdline(self):
        return ['sng']

    def feed_stdin(self, stdin):
        with open(self.path, 'rb') as f:
            for buf in iter(functools.partial(f.read, 32768), b''):
                stdin.write(buf)


class PngFile(File):
    RE_FILE_TYPE = re.compile(r'^PNG image data\b')

    def compare_details(self, other, source=None):
        sng_diff = Difference.from_command(Sng, self.path, other.path, source='sng')
        differences = [sng_diff]

        if sng_diff is not None and Config().compute_visual_diffs and \
                same_size(self, other):
            try:
                logger.debug(
                    "Generating visual difference for %s and %s",
                    self.path,
                    other.path,
                )
                content_diff = Difference(
                    None,
                    self.path,
                    other.path,
                    source="Image content",
                )
                content_diff.add_visuals([
                    pixel_difference(self.path, other.path),
                    flicker_difference(self.path, other.path),
                ])
                differences.append(content_diff)
            except subprocess.CalledProcessError:  # noqa
                pass

        return differences
