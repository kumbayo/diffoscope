# -*- coding: utf-8 -*-
#
# diffoscope: in-depth comparison of files, archives, and directories
#
# Copyright © 2015 Reiner Herrmann <reiner@reiner-h.de>
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

import pytest
import os
import tempfile

from diffoscope.config import Config
from diffoscope.comparators.missing_file import MissingFile
from diffoscope.comparators.fsimage import FsImageFile

from ..utils.data import load_fixture, get_data
from ..utils.tools import skip_unless_tools_exist, skip_unless_module_exists

img1 = load_fixture('test1.ext4')
img2 = load_fixture('test2.ext4')

@pytest.fixture(scope="session")
def guestfs_tempdir():
    import guestfs
    with tempfile.TemporaryDirectory(suffix='_diffoscope') as cachedir:
        g = guestfs.GuestFS(python_return_dict=True)
        g.set_cachedir(cachedir)
        # set cachedir for the diffoscope.comparators.fsimage module as well
        os.environ["LIBGUESTFS_CACHEDIR"] = cachedir
        g.add_drive_opts("/dev/null", format="raw", readonly=1)
        try:
            g.launch()
        except RuntimeError as e:
            # to debug this, set LIBGUESTFS_DEBUG=1 and give -s to pytest.
            # Unfortunately we can't capture the logs, due to capsys not being
            # available in a module/session scope, and g.set_event_callback
            # segfaults on my system.
            pytest.skip('guestfs not working on the system: %r' % e)
        yield cachedir

def test_identification(img1):
    assert isinstance(img1, FsImageFile)

@skip_unless_tools_exist('qemu-img')
@skip_unless_module_exists('guestfs')
def test_no_differences(img1, guestfs_tempdir):
    difference = img1.compare(img1)
    assert difference is None

@pytest.fixture
def differences(img1, img2, guestfs_tempdir):
    return img1.compare(img2).details

@skip_unless_tools_exist('qemu-img')
@skip_unless_module_exists('guestfs')
def test_differences(differences, guestfs_tempdir):
    assert differences[0].source1 == 'test1.ext4.tar'
    tarinfo = differences[0].details[0]
    tardiff = differences[0].details[1]
    encodingdiff = tardiff.details[0]
    assert tarinfo.source1 == 'file list'
    assert tarinfo.source2 == 'file list'
    assert tardiff.source1 == './date.txt'
    assert tardiff.source2 == './date.txt'
    assert encodingdiff.source1 == 'encoding'
    assert encodingdiff.source2 == 'encoding'
    expected_diff = get_data('ext4_expected_diffs')
    found_diff = tarinfo.unified_diff + tardiff.unified_diff + encodingdiff.unified_diff
    assert expected_diff == found_diff

@skip_unless_tools_exist('qemu-img')
@skip_unless_module_exists('guestfs')
def test_compare_non_existing(monkeypatch, img1, guestfs_tempdir):
    monkeypatch.setattr(Config(), 'new_file', True)
    difference = img1.compare(MissingFile('/nonexisting', img1))
    assert difference.source2 == '/nonexisting'
    assert difference.details[-1].source2 == '/dev/null'
