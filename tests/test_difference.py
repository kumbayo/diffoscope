# -*- coding: utf-8 -*-
#
# diffoscope: in-depth comparison of files, archives, and directories
#
# Copyright © 2015 Jérémy Bobbio <lunar@debian.org>
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

import io
import itertools
import pytest

from diffoscope.config import Config
from diffoscope.difference import Difference


def assert_size(diff, size):
    assert size == diff.size()
    assert size == sum(d.size_self() for d in diff.traverse_breadth())
    g = itertools.count()
    assert size == sum(d.size_self() for d in diff.traverse_heapq(lambda x, _: next(g)))

def assert_algebraic_properties(d, size):
    assert d.equals(d.get_reverse().get_reverse())
    assert d.get_reverse().size() == d.size() == size

def test_too_much_input_for_diff(monkeypatch):
    monkeypatch.setattr(Config(), 'max_diff_input_lines', 20)
    too_long_text_a = io.StringIO("a\n" * 21)
    too_long_text_b = io.StringIO("b\n" * 21)
    difference = Difference.from_text_readers(too_long_text_a, too_long_text_b, 'a', 'b')
    assert '[ Too much input for diff ' in difference.unified_diff
    assert_algebraic_properties(difference, 290)

def test_too_long_diff_block_lines(monkeypatch):
    monkeypatch.setattr(Config(), 'enforce_constraints', False)
    monkeypatch.setattr(Config(), 'max_diff_block_lines_saved', 10)
    too_long_text_a = io.StringIO("a\n" * 21)
    too_long_text_b = io.StringIO("b\n" * 21)
    difference = Difference.from_text_readers(too_long_text_a, too_long_text_b, 'a', 'b')
    assert '[ 11 lines removed ]' in difference.unified_diff
    assert_algebraic_properties(difference, 124)

def test_size_updates():
    d = Difference("0123456789", "path1", "path2")
    assert_size(d, 20)
    d.add_details([Difference("0123456789", "path1/a", "path2/a")])
    assert_size(d, 44)
    d.add_comment("lol1")
    assert_size(d, 48)

def test_traverse_heapq():
    d0 = Difference("0", "path1/a", "path2/a")
    d1 = Difference("012", "path1/b", "path2/b")
    d2 = Difference("01", "path1/c", "path2/c")
    d0.add_details([
        Difference("012345678", "path1/a/1", "path2/a/1"),
        Difference("0123", "path1/a/2", "path2/a/2"),
        Difference("012", "path1/a/3", "path2/a/3")])
    d1.add_details([
        Difference("01234567", "path1/b/1", "path2/b/1"),
        Difference("01234", "path1/b/2", "path2/b/2"),
        Difference("012345", "path1/b/3", "path2/b/3")])
    d2.add_details([
        Difference("01", "path1/c/1", "path2/c/1"),
        Difference("0123456789", "path1/c/2", "path2/c/2"),
        Difference("0123456", "path1/c/3", "path2/c/3")])
    diff = Difference("0123456789", "path1", "path2")
    diff.add_details([d0, d1, d2])
    # traverse nodes in depth order, but at a given depth traverse the nodes
    # there from smallest diff (counted non-recursively) to largest
    def f(node, parscore):
        depth = parscore[0] + 1 if parscore else 0
        return depth, node.size_self()
    assert_size(diff, 284)
    results = [d.source1[6:] for d in diff.traverse_heapq(f)]
    assert results == ['', 'a', 'c', 'b', 'c/1', 'a/3', 'a/2', 'b/2', 'b/3', 'c/3', 'b/1', 'a/1', 'c/2']

def test_non_str_arguments_to_source1_source2():
    for x in (
        (None, 'str'),
        ('str', None),
    ):
        a = io.StringIO('a')
        b = io.StringIO('b')

        with pytest.raises(TypeError):
            Difference.from_text_readers(a, b, *x)
