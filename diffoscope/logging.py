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

import logging


def setup_logging(debug, log_handler):
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG if debug else logging.WARNING)

    ch = log_handler or logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    logger.addHandler(ch)

    formatter = logging.Formatter(
        '%(asctime)s %(levelname).1s: %(name)s: %(message)s',
        '%Y-%m-%d %H:%M:%S',
    )
    ch.setFormatter(formatter)
