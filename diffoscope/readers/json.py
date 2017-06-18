# -*- coding: utf-8 -*-
#
# diffoscope: in-depth comparison of files, archives, and directories
#
# Copyright © 2017 Ximin Luo <infinity0@debian.org>
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
import codecs

from ..difference import Difference
from ..presenters.json import JSON_FORMAT_MAGIC

from .utils import UnrecognizedFormatError


class JSONReaderV1(object):
    def load(self, fp, fn):
        raw = json.load(codecs.getreader('utf-8')(fp))
        if JSON_FORMAT_MAGIC not in raw or raw[JSON_FORMAT_MAGIC] != 1:
            raise UnrecognizedFormatError(
                "Magic not found in JSON: {}".format(JSON_FORMAT_MAGIC)
            )
        return self.load_rec(raw)

    def load_rec(self, raw):
        source1 = raw['source1']
        source2 = raw['source2']
        unified_diff = raw['unified_diff']
        comments = raw.get('comments', [])
        details = [self.load_rec(child) for child in raw.get('details', [])]

        return Difference(
            unified_diff,
            source1,
            source2,
            comment=comments,
            details=details,
        )
