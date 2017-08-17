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

import base64
import codecs
import collections
import contextlib
import hashlib
import html
import io
import logging
import os
import re
import sys
from urllib.parse import urlparse

from diffoscope import VERSION
from diffoscope.config import Config
from diffoscope.diff import SideBySideDiff, DIFFON, DIFFOFF

from ..icon import FAVICON_BASE64
from ..utils import sizeof_fmt, PrintLimitReached, DiffBlockLimitReached, \
    create_limited_print_func, Presenter, make_printer, PartialString

from . import templates

# minimum line size, we add a zero-sized breakable space every
# LINESIZE characters
LINESIZE = 20
TABSIZE = 8

# Characters we're willing to word wrap on
WORDBREAK = " \t;.,/):-"

JQUERY_SYSTEM_LOCATIONS = (
    '/usr/share/javascript/jquery/jquery.js',
)

logger = logging.getLogger(__name__)
re_anchor_prefix = re.compile(r'^[^A-Za-z]')
re_anchor_suffix = re.compile(r'[^A-Za-z-_:\.]')


def send_and_exhaust(iterator, arg, default):
    """Send a single value to a coroutine, exhaust it, and return the final
    element or a default value if it was empty."""
    # Python's coroutine syntax is still a bit rough when you want to do
    # slightly more complex stuff. Watch this logic closely.
    output = default
    try:
        output = iterator.send(arg)
    except StopIteration:
        pass
    for output in iterator:
        pass
    return output

def md5(s):
    return hashlib.md5(s.encode('utf-8')).hexdigest()

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

def output_diff_path(path):
    return '/'.join(n.source1 for n in path[1:])

def output_anchor(path):
    return escape_anchor(output_diff_path(path))

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

def output_visual(visual, path, indentstr, indentnum):
    logger.debug('including image for %s', visual.source)
    indent = tuple(indentstr * (indentnum + x) for x in range(3))
    anchor = output_anchor(path)
    return u"""{0[0]}<div class="difference">
{0[1]}<div class="diffheader">
{0[1]}<div class="diffcontrol">⊟</div>
{0[1]}<div><span class="source">{1}</span>
{0[2]}<a class="anchor" href="#{2}" name="{2}">\xb6</a>
{0[1]}</div>
{0[1]}</div>
{0[1]}<div class="difference"><img src=\"data:{3},{4}\" alt=\"compared images\" /></div>
{0[0]}</div>""".format(indent, html.escape(visual.source), anchor, visual.data_type, visual.content)

def output_node_frame(difference, path, indentstr, indentnum, body):
    indent = tuple(indentstr * (indentnum + x) for x in range(3))
    anchor = output_anchor(path)
    dctrl_class, dctrl = ("diffcontrol", u'⊟') if difference.has_visible_children() else ("diffcontrol-nochildren", u'⊡')
    if difference.source1 == difference.source2:
        header = u"""{0[1]}<div class="{1}">{2}</div>
{0[1]}<div><span class="diffsize">{3}</span></div>
{0[1]}<div><span class="source">{5}</span>
{0[2]}<a class="anchor" href="#{4}" name="{4}">\xb6</a>
{0[1]}</div>
""".format(indent, dctrl_class, dctrl, sizeof_fmt(difference.size()), anchor,
        html.escape(difference.source1))
    else:
        header = u"""{0[1]}<div class="{1} diffcontrol-double">{2}</div>
{0[1]}<div><span class="diffsize">{3}</span></div>
{0[1]}<div><span class="source">{5}</span> vs.</div>
{0[1]}<div><span class="source">{6}</span>
{0[2]}<a class="anchor" href="#{4}" name="{4}">\xb6</a>
{0[1]}</div>
""".format(indent, dctrl_class, dctrl, sizeof_fmt(difference.size()), anchor,
        html.escape(difference.source1),
        html.escape(difference.source2))

    return PartialString.numl(u"""{0[1]}<div class="diffheader">
{1}{0[1]}</div>
{2}""", 3).pformatl(indent, header, body)

def output_node(ctx, difference, path, indentstr, indentnum):
    """Returns a tuple (parent, continuation) where

    - parent is a PartialString representing the body of the node, including
      its comments, visuals, unified_diff and headers for its children - but
      not the bodies of the children
    - continuation is either None or (only in html-dir mode) a function which
      when called with a single integer arg, the maximum size to print, will
      print any remaining "split" pages for unified_diff up to the given size.
    """
    indent = tuple(indentstr * (indentnum + x) for x in range(3))
    t, cont = PartialString.cont()

    comments = u""
    if difference.comments:
        comments = u'{0[1]}<div class="comment">\n{1}{0[1]}</div>\n'.format(
            indent, "".join(u"{0[2]}{1}<br/>\n".format(indent, html.escape(x)) for x in difference.comments))

    visuals = u""
    for visual in difference.visuals:
        visuals += output_visual(visual, path, indentstr, indentnum+1)

    udiff = u""
    ud_cont = None
    if difference.unified_diff:
        ud_cont = HTMLSideBySidePresenter().output_unified_diff(
            ctx, difference.unified_diff, difference.has_internal_linenos)
        udiff = next(ud_cont)
        if isinstance(udiff, PartialString):
            ud_cont = ud_cont.send
            udiff = udiff.pformatl(PartialString.of(ud_cont))
        else:
            for _ in ud_cont: pass # exhaust the iterator, avoids GeneratorExit
            ud_cont = None

    # PartialString for this node
    body = PartialString.numl(u"{0}{1}{2}{-1}", 3, cont).pformatl(comments, visuals, udiff)
    if len(path) == 1:
        # root node, frame it
        body = output_node_frame(difference, path, indentstr, indentnum, body)
    t = cont(t, body)

    # Add holes for child nodes
    for d in difference.details:
        child = output_node_frame(d, path + [d], indentstr, indentnum+1, PartialString.of(d))
        child = PartialString.numl(u"""{0[1]}<div class="difference">
{1}{0[1]}</div>
{-1}""", 2, cont).pformatl(indent, child)
        t = cont(t, child)

    assert len(t.holes) >= len(difference.details) + 1 # there might be extra holes for the unified diff continuation
    return cont(t, u""), ud_cont

def output_header(css_url, our_css_url=False, icon_url=None):
    if css_url:
        css_link = u'  <link href="%s" type="text/css" rel="stylesheet" />\n' % css_url
    else:
        css_link = u''
    if our_css_url:
        css_style = u'  <link href="%s" type="text/css" rel="stylesheet" />\n' % our_css_url
    else:
        css_style = u'<style type="text/css">\n' + templates.STYLES + u'</style>\n'
    if icon_url:
        favicon = icon_url
    else:
        favicon = u'data:image/png;base64,' + FAVICON_BASE64
    return templates.HEADER % {
        'title': html.escape(' '.join(sys.argv)),
        'favicon': favicon,
        'css_link': css_link,
        'css_style': css_style
    }

def output_footer(jquery_url=None):
    footer = templates.FOOTER % {'version': VERSION}
    if jquery_url:
        return templates.SCRIPTS % {'jquery_url': html.escape(jquery_url)} + footer
    return footer

@contextlib.contextmanager
def file_printer(directory, filename):
    with codecs.open(os.path.join(directory,filename), 'w', encoding='utf-8') as f:
        yield f.write

@contextlib.contextmanager
def spl_file_printer(directory, filename, accum):
    with codecs.open(os.path.join(directory,filename), 'w', encoding='utf-8') as f:
        print_func = f.write
        def recording_print_func(s):
            print_func(s)
            recording_print_func.bytes_written += len(s)
            accum.bytes_written += len(s)
        recording_print_func.bytes_written = 0
        yield recording_print_func


class HTMLPrintContext(collections.namedtuple("HTMLPrintContext",
    "target single_page jquery_url css_url our_css_url icon_url")):
    @property
    def directory(self):
        return None if self.single_page else self.target


class HTMLSideBySidePresenter(object):
    supports_visual_diffs = True

    def __init__(self):
        self.max_lines = Config().max_diff_block_lines # only for html-dir
        self.max_lines_parent = Config().max_page_diff_block_lines
        self.max_page_size_child = Config().max_page_size_child

    def new_unified_diff(self):
        self.spl_rows = 0
        self.spl_current_page = 0
        self.spl_print_func = None
        self.spl_print_ctrl = None
        # the below apply to child pages only, the parent page limit works
        # differently and is controlled by output_difference later below
        self.bytes_max_total = 0
        self.bytes_written = 0
        self.error_row = None

    def output_hunk_header(self, hunk_off1, hunk_size1, hunk_off2, hunk_size2):
        self.spl_print_func(u'<tr class="diffhunk"><td colspan="2">Offset %d, %d lines modified</td>' % (hunk_off1, hunk_size1))
        self.spl_print_func(u'<td colspan="2">Offset %d, %d lines modified</td></tr>\n' % (hunk_off2, hunk_size2))

    def output_line(self, has_internal_linenos, type_name, s1, line1, s2, line2):
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
            self.spl_print_func(u"</tr>\n")

    def spl_print_enter(self, print_context, rotation_params):
        # Takes ownership of print_context
        self.spl_print_ctrl = print_context.__exit__, rotation_params
        self.spl_print_func = print_context.__enter__()
        ctx, _ = rotation_params
        # Print file and table headers
        self.spl_print_func(output_header(ctx.css_url, ctx.our_css_url, ctx.icon_url))

    def spl_had_entered_child(self):
        return self.spl_print_ctrl and self.spl_print_ctrl[1] and self.spl_current_page > 0

    def spl_print_exit(self, *exc_info):
        if not self.spl_had_entered_child(): return False
        self.spl_print_func(output_footer())
        _exit, _ = self.spl_print_ctrl
        self.spl_print_func = None
        self.spl_print_ctrl = None
        return _exit(*exc_info)

    def check_limits(self):
        if not self.spl_print_ctrl[1]:
            # html-dir single output, don't need to rotate
            if self.spl_rows >= self.max_lines_parent:
                raise DiffBlockLimitReached()
            return False
        else:
            # html-dir output, perhaps need to rotate
            if self.spl_rows >= self.max_lines:
                raise DiffBlockLimitReached()

            if self.spl_current_page == 0: # on parent page
                if self.spl_rows < self.max_lines_parent:
                    return False
                logger.debug("new unified-diff subpage, parent page went over %s lines", self.max_lines_parent)
            else: # on child page
                if self.bytes_max_total and self.bytes_written > self.bytes_max_total:
                    raise PrintLimitReached()
                if self.spl_print_func.bytes_written < self.max_page_size_child:
                    return False
                logger.debug("new unified-diff subpage, previous subpage went over %s bytes", self.max_page_size_child)
            return True

    def new_child_page(self):
        _, rotation_params = self.spl_print_ctrl
        ctx, mainname = rotation_params
        self.spl_current_page += 1
        filename = "%s-%s.html" % (mainname, self.spl_current_page)

        if self.spl_current_page > 1:
            # previous page was a child, close it
            self.spl_print_func(templates.UD_TABLE_FOOTER % {"filename": html.escape(filename), "text": "load diff"})
            self.spl_print_func(u"</table>\n")
            self.spl_print_exit(None, None, None)

        # rotate to the next child page
        context = spl_file_printer(ctx.directory, filename, self)
        self.spl_print_enter(context, rotation_params)
        self.spl_print_func(templates.UD_TABLE_HEADER)

    def output_limit_reached(self, limit_type, total, bytes_processed):
        logger.debug('%s print limit reached', limit_type)
        bytes_left = total - bytes_processed
        self.error_row = templates.UD_TABLE_LIMIT_FOOTER % {
            "limit_type": limit_type,
            "bytes_left": bytes_left,
            "bytes_total": total,
            "percent": (bytes_left / total) * 100
        }
        self.spl_print_func(self.error_row)

    def output_unified_diff_table(self, unified_diff, has_internal_linenos):
        """Output a unified diff <table> possibly over multiple pages.

        It is the caller's responsibility to set up self.spl_* correctly.

        Yields None for each extra child page, and then True or False depending
        on whether the whole output was truncated.
        """
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
                self.spl_rows += 1
                if not self.check_limits():
                    continue
                self.new_child_page()
                new_limit = yield None
                if new_limit:
                    self.bytes_max_total = new_limit
                    self.bytes_written = 0
                    self.check_limits()
            wrote_all = True
        except GeneratorExit:
            return
        except DiffBlockLimitReached:
            self.output_limit_reached("diff block lines", len(unified_diff), ydiff.bytes_processed)
            wrote_all = False
        except PrintLimitReached:
            self.output_limit_reached("report size", len(unified_diff), ydiff.bytes_processed)
            wrote_all = False
        finally:
            # no footer on the last page, just a close tag
            self.spl_print_func(u"</table>")
        yield wrote_all

    def output_unified_diff(self, ctx, unified_diff, has_internal_linenos):
        self.new_unified_diff()
        rotation_params = None
        if ctx.directory:
            mainname = md5(unified_diff)
            rotation_params = ctx, mainname

        try:
            udiff = io.StringIO()
            udiff.write(templates.UD_TABLE_HEADER)
            self.spl_print_func = udiff.write
            self.spl_print_ctrl = None, rotation_params

            it = self.output_unified_diff_table(unified_diff, has_internal_linenos)
            wrote_all = next(it)
            if wrote_all is None:
                assert self.spl_current_page == 1
                # now pause the iteration and wait for consumer to give us a
                # size-limit to write the remaining pages with
                # exhaust the iterator and save the last item in wrote_all
                new_limit = yield PartialString(PartialString.escape(udiff.getvalue()) + u"{0}</table>\n", None)
                wrote_all = send_and_exhaust(it, new_limit, wrote_all)
            else:
                yield udiff.getvalue()
                return

        except GeneratorExit:
            logger.debug("skip extra output for unified diff %s", mainname)
            it.close()
            self.spl_print_exit(None, None, None)
            return
        except:
            import traceback
            traceback.print_exc()
            if self.spl_print_exit(*sys.exc_info()) is False: raise
        else:
            self.spl_print_exit(None, None, None)
        finally:
            self.spl_print_ctrl = None
            self.spl_print_func = None

        truncated = not wrote_all
        child_rows_written = self.spl_rows - self.max_lines_parent
        if truncated and not child_rows_written:
            # if we didn't write any child rows, just output the error message on the parent page
            parent_last_row = self.error_row
        else:
            noun = "pieces" if self.spl_current_page > 1 else "piece"
            text = "load diff (%s %s%s)" % (self.spl_current_page, noun, (", truncated" if truncated else ""))
            parent_last_row = templates.UD_TABLE_FOOTER % {"filename": html.escape("%s-1.html" % mainname), "text": text}
        yield self.bytes_written, parent_last_row


class HTMLPresenter(Presenter):
    supports_visual_diffs = True

    def __init__(self):
        self.reset()

    def reset(self):
        self.report_printed = 0
        self.report_limit = Config().max_report_size

    @property
    def report_remaining(self):
        return self.report_limit - self.report_printed

    def maybe_print(self, node, printers, outputs, continuations):
        output = outputs[node]
        node_cont = continuations[node]
        if output.holes and set(output.holes) - set(node_cont):
            return

        # could be slightly more accurate, whatever
        est_placeholder_len = max(len(templates.UD_TABLE_FOOTER), len(templates.UD_TABLE_LIMIT_FOOTER)) + 40
        est_size = output.size(est_placeholder_len)

        results = {}
        for cont in node_cont:
            remaining = self.report_remaining - est_size
            printed, result = cont(remaining)
            self.report_printed += printed
            results[cont] = result

        out = output.format(results)
        printer_args = printers[node]
        with printer_args[0](*printer_args[1:]) as printer:
            printer(out)
        self.report_printed += len(out)

        del outputs[node]
        del printers[node]
        del continuations[node]

    def output_node_placeholder(self, pagename, lazy_load, size=0):
        if lazy_load:
            return templates.DIFFNODE_LAZY_LOAD % {
                "pagename": pagename,
                "pagesize": sizeof_fmt(Config().max_page_size_child),
                "size": sizeof_fmt(size),
            }
        else:
            return templates.DIFFNODE_LIMIT

    def output_difference(self, ctx, root_difference):
        outputs = {} # nodes to their partial output
        ancestors = {} # child nodes to ancestor nodes
        placeholder_len = len(self.output_node_placeholder("XXXXXXXXXXXXXXXX", not ctx.single_page))
        continuations = {} # functions to print unified diff continuations (html-dir only)
        printers = {} # nodes to their printers

        def smallest_first(node, parscore):
            depth = parscore[0] + 1 if parscore else 0
            parents = parscore[3] if parscore else []
            # Difference is not comparable so use memory address in event of a tie
            return depth, node.size_self(), id(node), parents + [node]

        pruned = set() # children
        for node, score in root_difference.traverse_heapq(smallest_first, yield_score=True):
            if node in pruned:
                continue

            ancestor = ancestors.pop(node, None)
            path = score[3]
            diff_path = output_diff_path(path)
            pagename = md5(diff_path)
            logger.debug('html output for %s', diff_path)
            node_output, node_continuation = output_node(ctx, node, path, "  ", len(path)-1)

            add_to_existing = False
            if ancestor:
                page_limit = Config().max_page_size if ancestor is root_difference else Config().max_page_size_child
                page_current = outputs[ancestor].size(placeholder_len)
                report_current = self.report_printed + sum(p.size(placeholder_len) for p in outputs.values())
                want_to_add = node_output.size(placeholder_len)
                logger.debug("report size: %s/%s, page size: %s/%s, want to add %s)",
                    report_current, self.report_limit, page_current, page_limit, want_to_add)
                if report_current + want_to_add > self.report_limit:
                    make_new_subpage = False
                elif page_current + want_to_add < page_limit:
                    add_to_existing = True
                else:
                    make_new_subpage = not ctx.single_page

            if add_to_existing:
                # under limit, add it to an existing page
                outputs[ancestor] = outputs[ancestor].pformat({node: node_output})
                stored = ancestor

            else:
                # over limit (or root), new subpage or continue/break
                if ancestor:
                    placeholder = self.output_node_placeholder(pagename, make_new_subpage, node.size())
                    outputs[ancestor] = outputs[ancestor].pformat({node: placeholder})
                    self.maybe_print(ancestor, printers, outputs, continuations)
                    footer = output_footer()
                    if not make_new_subpage: # we hit a limit, either max-report-size or single-page
                        if not outputs:
                            # no more holes, don't traverse any more nodes
                            break
                        else:
                            # don't traverse this node's children, they won't be output
                            # however there are holes in other pages, so don't break just yet
                            for child in node.details:
                                pruned.add(child)
                            continue
                else:
                    # unconditionally write the root node regardless of limits
                    assert node is root_difference
                    footer = output_footer(ctx.jquery_url)
                    pagename = "index"

                outputs[node] = node_output.frame(
                    output_header(ctx.css_url, ctx.our_css_url, ctx.icon_url) +
                    u'<div class="difference">\n', u'</div>\n' + footer)
                assert not ctx.single_page or node is root_difference
                printers[node] = (make_printer, ctx.target) if ctx.single_page else (file_printer, ctx.target, "%s.html" % pagename)
                stored = node

            for child in node.details:
                ancestors[child] = stored

            conts = continuations.setdefault(stored, [])
            if node_continuation:
                conts.append(node_continuation)

            self.maybe_print(stored, printers, outputs, continuations)

        if outputs:
            import pprint
            pprint.pprint(outputs, indent=4)
        assert not outputs

    def ensure_jquery(self, jquery_url, basedir, default_override):
        if jquery_url is None:
            jquery_url = default_override
            default_override = None # later, we can detect jquery_url was None
        if jquery_url == 'disable' or not jquery_url:
            return None

        url = urlparse(jquery_url)
        if url.scheme or url.netloc:
            # remote path
            return jquery_url

        # local path
        if os.path.isabs(url.path):
            check_path = url.path
        else:
            check_path = os.path.join(basedir, url.path)

        if os.path.lexists(check_path):
            return url.path

        for path in JQUERY_SYSTEM_LOCATIONS:
            if os.path.exists(path):
                os.symlink(path, check_path)
                logger.debug('jquery found at %s and symlinked to %s', path, check_path)
                return url.path

        if default_override is None:
            # if no jquery_url was given, and we can't find it, don't use it
            return None

        logger.warning('--jquery given, but jQuery was not found. Using it regardless.')
        logger.debug('Locations searched: %s', ', '.join(JQUERY_SYSTEM_LOCATIONS))
        return url.path

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

        jquery_url = self.ensure_jquery(jquery_url, directory, "jquery.js")
        with open(os.path.join(directory, "common.css"), "w") as fp:
            fp.write(templates.STYLES)
        with open(os.path.join(directory, "icon.png"), "wb") as fp:
            fp.write(base64.b64decode(FAVICON_BASE64))
        ctx = HTMLPrintContext(directory, False, jquery_url, css_url, "common.css", "icon.png")
        self.output_difference(ctx, difference)


    def output_html(self, target, difference, css_url=None, jquery_url=None):
        """
        Default presenter, all in one HTML file
        """
        jquery_url = self.ensure_jquery(jquery_url, os.getcwd(), None)
        ctx = HTMLPrintContext(target, True, jquery_url, css_url, None, None)
        self.output_difference(ctx, difference)

    @classmethod
    def run(cls, data, difference, parsed_args):
        cls().output_html(
            parsed_args.html_output,
            difference,
            css_url=parsed_args.css_url,
            jquery_url=parsed_args.jquery_url,
        )


class HTMLDirectoryPresenter(HTMLPresenter):
    @classmethod
    def run(cls, data, difference, parsed_args):
        cls().output_html_directory(
            parsed_args.html_output_directory,
            difference,
            css_url=parsed_args.css_url,
            jquery_url=parsed_args.jquery_url,
        )
