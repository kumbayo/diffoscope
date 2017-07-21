# -*- coding: utf-8 -*-
#
# diffoscope: in-depth comparison of files, archives, and directories
#
# Copyright © 2017 Juliana Rodrigues <juliana.orod@gmail.com>
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

from xml.dom import minidom
from diffoscope.difference import Difference
from diffoscope.comparators.utils.file import File
from xml.parsers.expat import ExpatError

def _format(node):
    """
    Removes *inplace* spaces from minidom.Document

    Args:
        node -- A xml.dom.minidom.Document object

    Returns:
        void
    """
    for n in node.childNodes:
        if n.nodeType == minidom.Node.TEXT_NODE:
            if n.nodeValue: n.nodeValue = n.nodeValue.strip()
        elif n.nodeType == minidom.Node.ELEMENT_NODE:
            _format(n)

def _parse(file):
    """
    Formats a minidom.Document file and returns XML as string.

    Args:
        file -- An io.TextIOWrapper object

    Returns:
        str: formated string object
    """
    xml = minidom.parse(file)
    _format(xml)
    xml.normalize()
    return xml.toprettyxml(indent=2*' ')


class XMLFile(File):
    """
    XML Files Comparison class

    Attributes:
        RE_FILE_EXTENSION (SRE_Pattern): xml file extension pattern
    """
    RE_FILE_EXTENSION = re.compile(r'\.xml$')

    @staticmethod
    def recognizes(file):
        """
        Identifies if a given file has XML extension

        Args:
            file - a diffoscope.comparators.utils.file.File object

        Returns:
            False if file is not a XML File, True otherwise
        """
        if XMLFile.RE_FILE_EXTENSION.search(file.name) is None:
            return False

        with open(file.path) as f:
            try:
                file.parsed = _parse(f)
            except ExpatError:
                return False

        return True

    def compare_details(self, other, source=None):
        """
        Compares self.object with another, returning a Difference object

        Args:
            other    -- A XMLFile object
            source

        Returns:
            A diffoscope.difference.Difference object
        """
        return [ Difference.from_text(self.dumps(self), self.dumps(other),
            self.path, other.path)]

    def dumps(self, file):
        """
        Opens a XMLFile and returns its parsed content

        Args:
            file -- XMLFile object

        Returns:
            str -- Formatted XML content from file
        """
        if file.parsed:
            return file.parsed

        with open(file.path) as f:
            return _parse(f)


