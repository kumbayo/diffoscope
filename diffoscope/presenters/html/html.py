# -*- coding: utf-8 -*-
#
# diffoscope: in-depth comparison of files, archives, and directories
#
# Copyright © 2014-2015 Jérémy Bobbio <lunar@debian.org>
#           ©      2015 Reiner Herrmann <reiner@reiner-h.de>
#           © 2012-2013 Olivier Matz <zer0@droids-corp.org>
#           ©      2012 Alan De Smet <adesmet@cs.wisc.edu>
#           ©      2012 Sergey Satskiy <sergey.satskiy@gmail.com>
#           ©      2012 scito <info@scito.ch>
#
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
#
#
# Most of the code is borrowed from diff2html.py available at:
# http://git.droids-corp.org/?p=diff2html.git
#
# Part of the code is inspired by diff2html.rb from
# Dave Burt <dave (at) burt.id.au> (mainly for html theme)
#

import io
import os
import re
import sys
import html
import codecs
import hashlib
import logging
import contextlib

from diffoscope import VERSION
from diffoscope.config import Config
from diffoscope.diff import SideBySideDiff, DIFFON, DIFFOFF

from ..icon import FAVICON_BASE64
from ..utils import PrintLimitReached, DiffBlockLimitReached, \
    create_limited_print_func, Presenter, make_printer

from . import templates

# minimum line size, we add a zero-sized breakable space every
# LINESIZE characters
LINESIZE = 20
MAX_LINE_SIZE = 1024
TABSIZE = 8

# Characters we're willing to word wrap on
WORDBREAK = " \t;.,/):-"

JQUERY_SYSTEM_LOCATIONS = (
    '/usr/share/javascript/jquery/jquery.js',
)

logger = logging.getLogger(__name__)
re_anchor_prefix = re.compile(r'^[^A-Za-z]')
re_anchor_suffix = re.compile(r'[^A-Za-z-_:\.]')


def convert(s, ponct=0, tag=''):
    i = 0
    t = io.StringIO()
    for c in s:
        # used by diffs
        if c == DIFFON:
            t.write('<%s>' % tag)
        elif c == DIFFOFF:
            t.write('</%s>' % tag)

        # special highlighted chars
        elif c == "\t" and ponct == 1:
            n = TABSIZE-(i%TABSIZE)
            if n == 0:
                n = TABSIZE
            t.write('<span class="diffponct">\xbb</span>'+'\xa0'*(n-1))
        elif c == " " and ponct == 1:
            t.write('<span class="diffponct">\xb7</span>')
        elif c == "\n" and ponct == 1:
            t.write('<br/><span class="diffponct">\</span>')
        elif ord(c) < 32:
            conv = u"\\x%x" % ord(c)
            t.write('<em>%s</em>' % conv)
            i += len(conv)
        else:
            t.write(html.escape(c))
            i += 1

        if WORDBREAK.count(c) == 1:
            t.write('\u200b')
            i = 0
        if i > LINESIZE:
            i = 0
            t.write('\u200b')

    return t.getvalue()

def output_visual(print_func, visual, parents):
    logger.debug('including image for %s', visual.source)
    sources = parents + [visual.source]
    print_func(u'<div class="difference">')
    print_func(u'<div class="diffheader">')
    print_func(u'<div class="diffcontrol">⊟</div>')
    print_func(u'<div><span class="source">%s</span>'
               % html.escape(visual.source))
    anchor = escape_anchor('/'.join(sources[1:]))
    print_func(
        u' <a class="anchor" href="#%s" name="%s">\xb6</a>' % (anchor, anchor))
    print_func(u"</div>")
    print_func(u"</div>")
    print_func(u'<div class="difference">'
               u'<img src=\"data:%s,%s\" alt=\"compared images\" /></div>' %
               (visual.data_type, visual.content))
    print_func(u"</div>", force=True)

def escape_anchor(val):
    """
    ID and NAME tokens must begin with a letter ([A-Za-z]) and may be followed
    by any number of letters, digits ([0-9]), hyphens ("-"), underscores ("_"),
    colons (":"), and periods (".").
    """

    for pattern, repl in (
        (re_anchor_prefix, 'D'),
        (re_anchor_suffix, '-'),
    ):
        val = pattern.sub(repl, val)

    return val

def output_header(css_url, print_func):
    if css_url:
        css_link = '<link href="%s" type="text/css" rel="stylesheet" />' % css_url
    else:
        css_link = ''
    print_func(templates.HEADER % {'title': html.escape(' '.join(sys.argv)),
                         'favicon': FAVICON_BASE64,
                         'css_link': css_link,
                        })

def output_footer(print_func):
    print_func(templates.FOOTER % {'version': VERSION}, force=True)


@contextlib.contextmanager
def file_printer(directory, filename):
    with codecs.open(os.path.join(directory,filename), 'w', encoding='utf-8') as f:
        yield f.write

@contextlib.contextmanager
def spl_file_printer(directory, filename):
    with codecs.open(os.path.join(directory,filename), 'w', encoding='utf-8') as f:
        print_func = f.write
        def recording_print_func(s, force=False):
            print_func(s)
            recording_print_func.bytes_written += len(s)
        recording_print_func.bytes_written = 0
        yield recording_print_func


class HTMLPresenter(Presenter):
    supports_visual_diffs = True

    def __init__(self):
        self.new_unified_diff()

    def new_unified_diff(self):
        self.spl_rows = 0
        self.spl_current_page = 0
        self.spl_print_func = None
        self.spl_print_ctrl = None

    def output_hunk_header(self, hunk_off1, hunk_size1, hunk_off2, hunk_size2):
        self.spl_print_func(u'<tr class="diffhunk"><td colspan="2">Offset %d, %d lines modified</td>' % (hunk_off1, hunk_size1))
        self.spl_print_func(u'<td colspan="2">Offset %d, %d lines modified</td></tr>\n' % (hunk_off2, hunk_size2))
        self.row_was_output()

    def output_line(self, has_internal_linenos, type_name, s1, line1, s2, line2):
        if s1 and len(s1) > MAX_LINE_SIZE:
            s1 = s1[:MAX_LINE_SIZE] + u" ✂"
        if s2 and len(s2) > MAX_LINE_SIZE:
            s2 = s2[:MAX_LINE_SIZE] + u" ✂"

        self.spl_print_func(u'<tr class="diff%s">' % type_name)
        try:
            if s1:
                if has_internal_linenos:
                    self.spl_print_func(u'<td colspan="2" class="diffpresent">')
                else:
                    self.spl_print_func(u'<td class="diffline">%d </td>' % line1)
                    self.spl_print_func(u'<td class="diffpresent">')
                self.spl_print_func(convert(s1, ponct=1, tag='del'))
                self.spl_print_func(u'</td>')
            else:
                self.spl_print_func(u'<td colspan="2">\xa0</td>')

            if s2:
                if has_internal_linenos:
                    self.spl_print_func(u'<td colspan="2" class="diffpresent">')
                else:
                    self.spl_print_func(u'<td class="diffline">%d </td>' % line2)
                    self.spl_print_func(u'<td class="diffpresent">')
                self.spl_print_func(convert(s2, ponct=1, tag='ins'))
                self.spl_print_func(u'</td>')
            else:
                self.spl_print_func(u'<td colspan="2">\xa0</td>')
        finally:
            self.spl_print_func(u"</tr>\n", force=True)
            self.row_was_output()

    def spl_print_enter(self, print_context, rotation_params):
        # Takes ownership of print_context
        self.spl_print_ctrl = print_context.__exit__, rotation_params
        self.spl_print_func = print_context.__enter__()
        _, _, css_url = rotation_params
        # Print file and table headers
        output_header(css_url, self.spl_print_func)

    def spl_had_entered_child(self):
        return self.spl_print_ctrl and self.spl_print_ctrl[1] and self.spl_current_page > 0

    def spl_print_exit(self, *exc_info):
        if not self.spl_had_entered_child(): return False
        output_footer(self.spl_print_func)
        _exit, _ = self.spl_print_ctrl
        self.spl_print_func = None
        self.spl_print_ctrl = None
        return _exit(*exc_info)

    def row_was_output(self):
        self.spl_rows += 1
        _, rotation_params = self.spl_print_ctrl
        max_lines = Config().max_diff_block_lines
        max_lines_parent = Config().max_diff_block_lines_parent
        max_lines_ratio = Config().max_diff_block_lines_html_dir_ratio
        max_report_child_size = Config().max_report_child_size
        if not rotation_params:
            # html-dir single output, don't need to rotate
            if self.spl_rows >= max_lines:
                raise DiffBlockLimitReached()
            return
        else:
            # html-dir output, perhaps need to rotate
            directory, mainname, css_url = rotation_params
            if self.spl_rows >= max_lines_ratio * max_lines:
                raise DiffBlockLimitReached()

            if self.spl_current_page == 0: # on parent page
                if self.spl_rows < max_lines_parent:
                    return
            else: # on child page
                # TODO: make this stay below the max, instead of going 1 row over the max
                # will require some backtracking...
                if self.spl_print_func.bytes_written < max_report_child_size:
                    return

        self.spl_current_page += 1
        filename = "%s-%s.html" % (mainname, self.spl_current_page)

        if self.spl_current_page > 1:
            # previous page was a child, close it
            self.spl_print_func(templates.UD_TABLE_FOOTER % {"filename": html.escape(filename), "text": "load diff"}, force=True)
            self.spl_print_exit(None, None, None)

        # rotate to the next child page
        context = spl_file_printer(directory, filename)
        self.spl_print_enter(context, rotation_params)
        self.spl_print_func(templates.UD_TABLE_HEADER)

    def output_unified_diff_table(self, unified_diff, has_internal_linenos):
        self.spl_print_func(templates.UD_TABLE_HEADER)
        try:
            ydiff = SideBySideDiff(unified_diff)
            for t, args in ydiff.items():
                if t == "L":
                    self.output_line(has_internal_linenos, *args)
                elif t == "H":
                    self.output_hunk_header(*args)
                elif t == "C":
                    self.spl_print_func(u'<td colspan="2">%s</td>\n' % args)
                else:
                    raise AssertionError()
            return True
        except DiffBlockLimitReached:
            total = len(unified_diff)
            bytes_left = total - ydiff.bytes_processed
            frac = bytes_left / total
            self.spl_print_func(
                u'<tr class="error">'
                u'<td colspan="4">Max diff block lines reached; %s/%s bytes (%.2f%%) of diff not shown.'
                u"</td></tr>" % (bytes_left, total, frac*100), force=True)
            return False
        except PrintLimitReached:
            assert not self.spl_had_entered_child() # limit reached on the parent page
            self.spl_print_func(u'<tr class="error"><td colspan="4">Max output size reached.</td></tr>', force=True)
            raise
        finally:
            self.spl_print_func(u"</table>", force=True)

    def output_unified_diff(self, print_func, css_url, directory, unified_diff, has_internal_linenos):
        self.new_unified_diff()
        rotation_params = None
        if directory:
            mainname = hashlib.md5(unified_diff.encode('utf-8')).hexdigest()
            rotation_params = directory, mainname, css_url
        try:
            self.spl_print_func = print_func
            self.spl_print_ctrl = None, rotation_params
            truncated = not self.output_unified_diff_table(unified_diff, has_internal_linenos)
        except:
            if not self.spl_print_exit(*sys.exc_info()): raise
        else:
            self.spl_print_exit(None, None, None)
        finally:
            self.spl_print_ctrl = None
            self.spl_print_func = None

        if self.spl_current_page > 0:
            noun = "pieces" if self.spl_current_page > 1 else "piece"
            text = "load diff (%s %s%s)" % (self.spl_current_page, noun, (", truncated" if truncated else ""))
            print_func(templates.UD_TABLE_FOOTER % {"filename": html.escape("%s-1.html" % mainname), "text": text}, force=True)

    def output_difference(self, difference, print_func, css_url, directory, parents):
        logger.debug('html output for %s', difference.source1)
        sources = parents + [difference.source1]
        print_func(u'<div class="difference">')
        try:
            print_func(u'<div class="diffheader">')
            diffcontrol = ("diffcontrol", u'⊟') if difference.has_visible_children() else ("diffcontrol-nochildren", u'⊡')
            if difference.source1 == difference.source2:
                print_func(u'<div class="%s">%s</div>' % diffcontrol)
                print_func(u'<div><span class="source">%s</span>'
                           % html.escape(difference.source1))
            else:
                print_func(u'<div class="%s diffcontrol-double">%s</div>' % diffcontrol)
                print_func(u'<div><span class="source">%s</span> vs.</div>'
                           % html.escape(difference.source1))
                print_func(u'<div><span class="source">%s</span>'
                           % html.escape(difference.source2))
            anchor = escape_anchor('/'.join(sources[1:]))
            print_func(u' <a class="anchor" href="#%s" name="%s">\xb6</a>' % (anchor, anchor))
            print_func(u"</div>")
            if difference.comments:
                print_func(u'<div class="comment">%s</div>'
                           % u'<br />'.join(map(html.escape, difference.comments)))
            print_func(u"</div>")
            if len(difference.visuals) > 0:
                for visual in difference.visuals:
                    output_visual(print_func, visual, sources)
            elif difference.unified_diff:
                self.output_unified_diff(print_func, css_url, directory, difference.unified_diff, difference.has_internal_linenos)
            for detail in difference.details:
                self.output_difference(detail, print_func, css_url, directory, sources)
        except PrintLimitReached:
            logger.debug('print limit reached')
            raise
        finally:
            print_func(u"</div>", force=True)

    def output_html(self, difference, css_url=None, print_func=None):
        """
        Default presenter, all in one HTML file
        """
        if print_func is None:
            print_func = print
        print_func = create_limited_print_func(print_func, Config().max_report_size)
        try:
            output_header(css_url, print_func)
            self.output_difference(difference, print_func, css_url, None, [])
        except PrintLimitReached:
            logger.debug('print limit reached')
            print_func(u'<div class="error">Max output size reached.</div>',
                       force=True)
        output_footer(print_func)

    @classmethod
    def run(cls, data, difference, parsed_args):
        with make_printer(parsed_args.html_output) as fn:
            cls().output_html(
                difference,
                css_url=parsed_args.css_url,
                print_func=fn,
            )


class HTMLDirectoryPresenter(HTMLPresenter):

    def output_html_directory(self, directory, difference, css_url=None, jquery_url=None):
        """
        Multi-file presenter. Writes to a directory, and puts large diff tables
        into files of their own.

        This uses jQuery. By default it uses /usr/share/javascript/jquery/jquery.js
        (symlinked, so that you can still share the result over HTTP).
        You can also pass --jquery URL to diffoscope to use a central jQuery copy.
        """
        if not os.path.exists(directory):
            os.makedirs(directory)

        if not os.path.isdir(directory):
            raise ValueError("%s is not a directory" % directory)

        if not jquery_url:
            jquery_symlink = os.path.join(directory, "jquery.js")
            if os.path.exists(jquery_symlink):
                jquery_url = "./jquery.js"
            else:
                if os.path.lexists(jquery_symlink):
                    os.unlink(jquery_symlink)
                for path in JQUERY_SYSTEM_LOCATIONS:
                    if os.path.exists(path):
                        os.symlink(path, jquery_symlink)
                        jquery_url = "./jquery.js"
                        break
                if not jquery_url:
                    logger.warning('--jquery was not specified and jQuery was not found in any known location. Disabling on-demand inline loading.')
                    logger.debug('Locations searched: %s', ', '.join(JQUERY_SYSTEM_LOCATIONS))
        if jquery_url == 'disable':
            jquery_url = None

        with file_printer(directory, "index.html") as print_func:
            print_func = create_limited_print_func(print_func, Config().max_report_size)
            try:
                output_header(css_url, print_func)
                self.output_difference(difference, print_func, css_url, directory, [])
            except PrintLimitReached:
                logger.debug('print limit reached')
                print_func(u'<div class="error">Max output size reached.</div>',
                           force=True)
            if jquery_url:
                print_func(templates.SCRIPTS % {'jquery_url': html.escape(jquery_url)}, force=True)
            output_footer(print_func)

    @classmethod
    def run(cls, data, difference, parsed_args):
        cls().output_html_directory(
            parsed_args.html_output_directory,
            difference,
            css_url=parsed_args.css_url,
            jquery_url=parsed_args.jquery_url,
        )
