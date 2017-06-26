# -*- coding: utf-8 -*-
#
# diffoscope: in-depth comparison of files, archives, and directories
#
# Copyright © 2015 Reiner Herrmann <reiner@reiner-h.de>
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


class Config(object):
    # GNU diff cannot process arbitrary large files :(
    max_diff_input_lines = 2 ** 22
    max_diff_block_lines_saved = float("inf")

    # hard limits, restricts single-file and multi-file formats
    max_report_size = 40 * 2 ** 20 # 40 MB
    max_diff_block_lines = 2 ** 10 # 1024 lines
    # structural limits, restricts single-file formats
    # semi-restricts multi-file formats
    max_page_size = 400 * 2 ** 10 # 400 kB
    max_page_size_child = 200 * 2 ** 10 # 200 kB
    max_page_diff_block_lines = 2 ** 7 # 128 lines

    max_text_report_size = 0

    new_file = False
    fuzzy_threshold = 60
    enforce_constraints = True
    excludes = ()
    exclude_commands = ()
    exclude_directory_metadata = False
    compute_visual_diffs = False
    max_container_depth = 50

    _singleton = {}

    def __init__(self):
        self.__dict__ = self._singleton

    def __setattr__(self, k, v):
        super(Config, self).__setattr__(k, v)

    def check_ge(self, a, b):
        va = getattr(self, a)
        vb = getattr(self, b)
        if va < vb:
            raise ValueError("{0} ({1}) cannot be smaller than {2} ({3})".format(a, va, b, vb))

    def check_constraints(self):
        self.check_ge("max_diff_block_lines", "max_page_diff_block_lines")
        self.check_ge("max_report_size", "max_page_size")
        self.check_ge("max_report_size", "max_page_size_child")
