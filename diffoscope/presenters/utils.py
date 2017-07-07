# -*- coding: utf-8 -*-
#
# diffoscope: in-depth comparison of files, archives, and directories
#
# Copyright © 2016, 2017 Chris Lamb <lamby@debian.org>
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

import sys
import codecs
import collections
import contextlib
import string
import _string


def round_sigfig(num, s):
    # https://stackoverflow.com/questions/3410976/how-to-round-a-number-to-significant-figures-in-python
    # This was too painful :/
    x = float(('%%.%sg' % s) % num)
    return x if abs(x) < (10**(s-1)) else int(x)


def sizeof_fmt(num, suffix='B', sigfig=3):
    # https://stackoverflow.com/questions/1094841/reusable-library-to-get-human-readable-version-of-file-size
    # A more powerful version is python3-hurry.filesize but that's an extra dependency
    for unit in ['','K','M','G','T','P','E','Z']:
        if abs(num) < 1024.0:
            break
        num /= 1024.0
    else:
        unit = 'Y'
    return "%s %s%s" % (round_sigfig(num, sigfig), unit, suffix)


class Presenter(object):
    supports_visual_diffs = False

    def __init__(self):
        self.depth = 0

    @classmethod
    def run(cls, data, difference, parsed_args):
        with make_printer(data['target']) as fn:
            cls(fn).start(difference)

    def start(self, difference):
        self.visit(difference)

    def visit(self, difference):
        self.visit_difference(difference)

        self.depth += 1

        for x in difference.details:
            self.visit(x)

        self.depth -= 1

    def visit_difference(self, difference):
        raise NotImplementedError()

    @classmethod
    def indent(cls, val, prefix):
        # As an optimisation, output as much as possible in one go to avoid
        # unnecessary splitting, interpolating, etc.
        #
        # We don't use textwrap.indent as that unnecessarily calls
        # str.splitlines, etc.
        return prefix + val.rstrip().replace('\n', '\n{}'.format(prefix))


class PrintLimitReached(Exception):
    pass


class DiffBlockLimitReached(Exception):
    pass


@contextlib.contextmanager
def make_printer(path):
    output = sys.stdout

    if path != '-':
        output = codecs.open(path, 'w', encoding='utf-8')

    def fn(*args, **kwargs):
        kwargs['file'] = output
        print(*args, **kwargs)
    fn.output = output

    yield fn

    if path != '-':
        output.close()


def create_limited_print_func(print_func, max_page_size):
    count = [0]

    def fn(val, force=False):
        print_func(val)

        if force or max_page_size == 0:
            return

        count[0] += len(val)
        if count[0] >= max_page_size:
            raise PrintLimitReached()

    return fn


class PartialFormatter(string.Formatter):

    @staticmethod
    def escape(x):
        return x.replace("}", "}}").replace("{", "{{")

    def get_value(self, key, args, kwargs):
        return args[key] if isinstance(key, int) else args[int(key)]

    def arg_of_field_name(self, field_name, args):
        x = int(_string.formatter_field_name_split(field_name)[0])
        return x if x >= 0 else len(args) + x

    def parse(self, *args, **kwargs):
        # Preserve {{ and }} escapes when formatting
        return map(lambda x: (self.escape(x[0]),) + x[1:], super().parse(*args, **kwargs))

    parse_no_escape = string.Formatter.parse


class FormatPlaceholder(object):

    def __init__(self, ident):
        self.ident = str(ident)

    def __repr__(self):
        return "%s(%r)" % (self.__class__.__name__, self.ident)

    def __format__(self, spec):
        result = self.ident
        if spec:
            result += ":" + spec
        return "{" + result + "}"

    def __getitem__(self, key):
        return FormatPlaceholder(self.ident + "[" + str(key) + "]")

    def __getattr__(self, attr):
        return FormatPlaceholder(self.ident + "." + str(attr))


class PartialString(object):
    r"""A format string where the "holes" are indexed by arbitrary python
    objects instead of string names or integer indexes. This is useful when you
    need to compose these objects together, but don't want users of the partial
    string to have to deal with artificial "indexes" for the holes.

    For example:

    >>> a, b = object(), object()
    >>> tmpl = PartialString("{0} {1}", a, b)
    >>> tmpl
    PartialString('{0} {1}', <object object at ...>, <object object at ...>)
    >>> tmpl.holes == (a, b)
    True
    >>> tmpl.format({a: "Hello,", b: "World!"})
    'Hello, World!'

    You can partially fill up the holes:

    >>> tmpl.pformat({a: "Hello,"}) == PartialString('Hello, {0}', b)
    True
    >>> tmpl.pformat({b: "World!"}) == PartialString('{0} World!', a)
    True

    You can estimate the size of the filled-up string:

    >>> tmpl.base_len, tmpl.num_holes
    (1, 2)
    >>> tmpl.size(hole_size=33)
    67

    You can also partially fill up the holes using more PartialStrings,
    even recursively:

    >>> tmpl.pformat({a: PartialString('{0}', b)}) == PartialString('{0} {0}', b)
    True
    >>> tmpl.pformat({a: tmpl}) == PartialString('{0} {1} {1}', a, b)
    True
    >>> tmpl.pformat({b: tmpl}) == PartialString('{0} {0} {1}', a, b)
    True

    Finally, the holes have to match what's in the format string:

    >>> tmpl = PartialString("{0} {1} {2}", a, b)
    Traceback (most recent call last):
    ...
    IndexError: tuple index out of range

    If you don't have specific objects to index the holes with, and don't want
    to create artifical indexes as in the above examples, here is a slightly
    simpler way of doing it:

    >>> tmpl = PartialString.numl("{0} {1} {2}", 2, object())
    >>> tmpl.holes
    (0, 1, <object ...>)
    >>> tmpl.pformatl("(first hole)", "(second hole)", "(object hole)")
    PartialString('(first hole) (second hole) (object hole)',)

    CORNER CASES:

    1. If you need to include a literal '{' or '}' in the resulting formatted
    string, you need to give them as "{{" or "}}" respectively in the fmtstr
    parameter of PartialString.__init__. PartialString.escape() might help to
    make this a bit easier:

    >>> tmpl = PartialString.numl("find {0} -name {1} " +
    ...            PartialString.escape("-exec ls -la {} \;"), 2)
    >>> tmpl
    PartialString('find {0} -name {1} -exec ls -la {{}} \\;', ...)
    >>> tmpl.size(), tmpl.size(4)
    (33, 39)

    When using pformat, any string arguments will be escaped automatically. You
    can take advantage of this to simplify the above example:

    >>> tmpl2 = PartialString.numl("find {0} -name {1} -exec ls -la {2} \;", 3)
    >>> tmpl2 = tmpl2.pformat({2: "{}"})
    >>> tmpl2 == tmpl
    True

    As long as you only use pformat, any "{{" "}}" literals will remain escaped
    in the resulting PartialString. They only become unescaped after going
    through a full format.

    >>> tmpl.pformatl("my{}path", "my{}file")
    PartialString('find my{{}}path -name my{{}}file -exec ls -la {{}} \\;',)
    >>> tmpl.formatl("my{}path", "my{}file")
    'find my{}path -name my{}file -exec ls -la {} \\;'

    CAVEATS:

    1. Filling up holes using other PartialStrings, does not play very nicely
    with format specifiers. For example:

    >>> tmpl = PartialString("{0:20} {1.child}", a, b)
    >>> tmpl.pformat({a: tmpl})
    PartialString('{0:20} {1.child}     {1.child}', <object ...>, <object ...>)
    >>> tmpl.pformat({b: tmpl})
    Traceback (most recent call last):
    ...
    AttributeError: ... has no attribute 'child'

    So you probably want to avoid such usages. The exact behaviour of these
    might change in the future, too.
    """
    formatter = PartialFormatter()
    escape = staticmethod(PartialFormatter.escape)

    def __init__(self, fmtstr="", *holes):
        # Ensure the format string is valid, and figure out some basic stats
        fmt = self.formatter
        # use parse_no_escape so lengths are preserved
        pieces = [(len(l), f) for l, f, _, _ in fmt.parse_no_escape(fmtstr)]
        used_args = set(fmt.arg_of_field_name(f, holes) for _, f in pieces if f is not None)
        self.num_holes = sum(1 for _, f in pieces if f is not None)
        self.base_len = sum(l for l, _ in pieces)

        # Remove unused and duplicates in the holes objects
        seen = collections.OrderedDict()
        mapping = tuple(FormatPlaceholder(seen.setdefault(k, len(seen))) if i in used_args else None
            for i, k in enumerate(holes))
        self._fmtstr = fmt.vformat(fmtstr, mapping, None)
        self.holes = tuple(seen.keys())

    def __eq__(self, other):
        return (self is other or isinstance(other, PartialString) and
                other._fmtstr == self._fmtstr and
                other.holes == self.holes)

    def __repr__(self):
        return "%s%r" % (self.__class__.__name__, (self._fmtstr,) + self.holes)

    def _format(self, *mapping):
        # format a string but preserve {{ and }} escapes
        return self.formatter.vformat(self._fmtstr, mapping, None)

    def _offset_fmtstr(self, offset):
        return self._format(*(FormatPlaceholder(i + offset) for i in range(len(self.holes))))

    def _pformat(self, mapping, escapestr):
        new_holes = []
        real_mapping = []
        for i, k in enumerate(self.holes):
            if k in mapping:
                v = mapping[k]
                if isinstance(v, PartialString):
                    out = v._offset_fmtstr(len(new_holes))
                    new_holes.extend(v.holes)
                elif isinstance(v, str) and escapestr:
                    out = PartialString.escape(v)
                else:
                    out = v
            else:
                out = FormatPlaceholder(len(new_holes))
                new_holes.append(k)
            real_mapping.append(out)
        return real_mapping, new_holes

    def size(self, hole_size=1):
        return self.base_len + hole_size * self.num_holes

    def pformat(self, mapping={}):
        """Partially apply a mapping, returning a new PartialString."""
        real_mapping, new_holes = self._pformat(mapping, True)
        return self.__class__(self._format(*real_mapping), *new_holes)

    def pformatl(self, *args):
        """Partially apply a list, implicitly mapped from self.holes."""
        return self.pformat(dict(zip(self.holes, args)))

    def format(self, mapping={}):
        """Fully apply a mapping, returning a string."""
        real_mapping, new_holes = self._pformat(mapping, False)
        if new_holes:
            raise ValueError("not all holes filled: %r" % new_holes)
        return self._fmtstr.format(*real_mapping)

    def formatl(self, *args):
        """Fully apply a list, implicitly mapped from self.holes."""
        return self.format(dict(zip(self.holes, args)))

    @classmethod
    def of(cls, obj):
        """Create a partial string for a single object.

        >>> e = PartialString.of(None)
        >>> e.pformat({None: e}) == e
        True
        """
        return cls("{0}", obj)

    @classmethod
    def numl(cls, fmtstr="", nargs=0, *holes):
        """Create a partial string with some implicit numeric holes.

        Useful in conjuction with PartialString.pformatl.

        >>> PartialString.numl("{0}{1}{2}{3}", 3, "last object")
        PartialString('{0}{1}{2}{3}', 0, 1, 2, 'last object')
        >>> _.pformatl(40, 41, 42, "final")
        PartialString('404142final',)
        """
        return cls(fmtstr, *range(nargs), *holes)

    @classmethod
    def cont(cls):
        r"""Create a new empty partial string with a continuation token.

        Construct a larger partial string from smaller pieces, without having
        to keep explicit track of a global index in between pieces. Instead,
        you can use per-piece local indexes, plus the special index {-1} to
        refer to where the next piece will go - or omit it to end the sequence.

        >>> t, cont = PartialString.cont()
        >>> t = cont(t, "x: {0}\ny: {1}\n{-1}", object(), object())
        >>> t = cont(t, "z: {0}\n{-1}", object())
        >>> t = cont(t, "")
        >>> key = t.holes
        >>> t.format({key[0]: "line1", key[1]: "line2", key[2]: "line3"})
        'x: line1\ny: line2\nz: line3\n'
        >>> t.size(hole_size=5)
        27
        """
        def cont(t, fmtstr, *holes):
            if isinstance(fmtstr, cls):
                return t.pformat({cont: fmtstr})
            else:
                return t.pformat({cont: cls(fmtstr, *(holes + (cont,)))})
        return cls("{0}", cont), cont

    def frame(self, header, footer):
        frame = self.__class__(self.escape(header) + "{0}" + self.escape(footer), None)
        return frame.pformat({None: self})


if __name__ == "__main__":
    import doctest
    doctest.testmod(optionflags=doctest.ELLIPSIS)
    a, b = object(), object()
    tmpl = PartialString("{0} {1}", a, b)
    t, cont = PartialString.cont()
