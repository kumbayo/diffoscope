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
import subprocess
import logging

from diffoscope.tools import tool_required
from diffoscope.difference import Difference
from diffoscope.config import Config

from .utils.file import File
from .utils.command import Command
from .image import pixel_difference, flicker_difference, get_image_size

logger = logging.getLogger(__name__)


class Gifbuild(Command):
    RE_FILTERS = (
        re.compile(r'^# GIF information from'),
        re.compile(r'^# End of .* dump'),
    )

    @tool_required('gifbuild')
    def cmdline(self):
        return ['gifbuild', '-d', self.path]

    def filter(self, line):
        if any(x.match(line.decode('utf-8')) for x in self.RE_FILTERS):
            return b""
        return line

@tool_required('identify')
def is_image_static(image_path):
    return subprocess.check_output(('identify', '-format',
                                    '%n', image_path)) == b'1'

class GifFile(File):
    RE_FILE_TYPE = re.compile(r'^GIF image data\b')

    def compare_details(self, other, source=None):
        gifbuild_diff = Difference.from_command(
            Gifbuild,
            self.path,
            other.path,
            source='gifbuild',
        )
        differences = [gifbuild_diff]
        if (gifbuild_diff is not None) and Config().html_output and \
                (get_image_size(self.path) == get_image_size(other.path)):
            try:
                own_size = get_image_size(self.path)
                other_size = get_image_size(other.path)
                self_static = is_image_static(self.path)
                other_static = is_image_static(other.path)
                if (own_size == other_size) and self_static and other_static:
                    logger.debug('Generating visual difference for %s and %s',
                                 self.path, other.path)
                    content_diff = Difference(None, self.path, other.path,
                                              source='Image content')
                    content_diff.add_visuals([pixel_difference(self.path, other.path),
                                             flicker_difference(self.path, other.path)])
                    differences.append(content_diff)
            except subprocess.CalledProcessError:  #noqa
                pass
        return differences
