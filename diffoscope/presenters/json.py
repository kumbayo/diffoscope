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

import json
from collections import OrderedDict

from .utils import Presenter

JSON_FORMAT_VERSION = 1
JSON_FORMAT_MAGIC = "diffoscope-json-version"


class JSONPresenter(Presenter):
    def __init__(self, print_func):
        self.stack = []
        self.print_func = print_func

        super().__init__()

    def start(self, difference):
        root = []
        self.stack = [root]
        super().start(difference)

        root[0][JSON_FORMAT_MAGIC] = JSON_FORMAT_VERSION
        root[0].move_to_end(JSON_FORMAT_MAGIC, last=False)
        self.print_func(json.dumps(root[0], indent=2))

    def visit_difference(self, difference):
        while self.depth + 1 < len(self.stack):
            self.stack.pop()

        elements = [
            ('source1', difference.source1),
            ('source2', difference.source2)
        ]
        if difference.comments:
            elements += [('comments', [x for x in difference.comments])]
        if difference.has_internal_linenos:
            elements += [('has_internal_linenos', True)]
        elements += [('unified_diff', difference.unified_diff)]

        child_differences = []
        if difference.details:
            elements += [('details', child_differences)]

        self.stack[-1].append(OrderedDict(elements))
        if difference.details:
            self.stack.append(child_differences)
