# -*- coding: utf-8 -*-
#
# Copyright (C) 2006-2007 Alec Thomas <alec@swapoff.org>
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution.
#

"""Console/terminal interaction classes and functions.

This module provides a simple formatting syntax for basic terminal visual
control sequences. The syntax is a carat ``^`` followed by a single character.

Valid colour escape sequences are:

    :``^N``: Reset all formatting.
    :``^B``: Toggle bold.
    :``^U``: Toggle underline.
    :``^0``: Set black foreground.
    :``^1``: Set red foreground.
    :``^2``: Set green foreground.
    :``^3``: Set brown foreground.
    :``^4``: Set blue foreground.
    :``^5``: Set magenta foreground.
    :``^6``: Set cyan foreground.
    :``^7``: Set white foreground.

"""

import re
import sys
import os
import codecs


__all__ = """
cwrite getch cerror cfatal register_codec cinfo cjustify clen cprint csplice
cwarning cwraptext print_table rjustify termheight termwidth wraptoterm cstrip
cencode cdecode
""".split()

__docformat__ = 'restructuredtext en'


_decode_re = re.compile(r'\^([N0-7BU])|[^^]+|\^')
_encode_re = re.compile(r'\033(?:[^[]|$)|\033\[(.*?)m')
_cstrip_re = re.compile(r'\^([N0-7BU])')
_cwrap_re = re.compile(r'(\n)|(\s+)|((?:\^[N0-7BU]|\S)+\b[^\n^\w]*)|(.)')
_terminal_type = None
_terminal_colours = 0


try:
    _stdout_is_a_tty = sys.stdout.isatty()
except:
    _stdout_is_a_tty = False

def mono_cwrite(io, text):
    io.write(_cstrip_re.sub('', text))


if 'darwin' != sys.platform and 'win' in sys.platform:
    _terminal_type = 'win'
    import msvcrt
    def getch():
        """Get a single character from the terminal."""
        return msvcrt.getch()

    # Appropriated from
    #   http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/496901
    STD_INPUT_HANDLE = -10
    STD_OUTPUT_HANDLE= -11
    STD_ERROR_HANDLE = -12

    FOREGROUND_BLUE = 0x01 # text color contains blue.
    FOREGROUND_GREEN= 0x02 # text color contains green.
    FOREGROUND_RED  = 0x04 # text color contains red.
    FOREGROUND_WHITE = FOREGROUND_BLUE | FOREGROUND_GREEN | FOREGROUND_RED
    FOREGROUND_INTENSITY = 0x08 # text color is intensified.
    BACKGROUND_BLUE = 0x10 # background color contains blue.
    BACKGROUND_GREEN= 0x20 # background color contains green.
    BACKGROUND_RED  = 0x40 # background color contains red.
    BACKGROUND_INTENSITY = 0x80 # background color is intensified.
    BACKGROUND_WHITE = BACKGROUND_BLUE | BACKGROUND_GREEN | BACKGROUND_RED

    try:
        import ctypes

        _stdout_handle = ctypes.windll.kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
        _stderr_handle = ctypes.windll.kernel32.GetStdHandle(STD_ERROR_HANDLE)

        def _set_windows_colour(color, fd=None):
            """(color) -> BOOL

            Example: set_color(FOREGROUND_GREEN | FOREGROUND_INTENSITY)
            """
            if not fd or fd is sys.stdout:
                handle = _stdout_handle
            elif fd is sys.stderr:
                handle = _stderr_handle
            else:
                return False
            bool = ctypes.windll.kernel32.SetConsoleTextAttribute(handle, color)
            return bool


        def cwrite(io, text):
            colour_map = {
                '0': 0,
                '1': FOREGROUND_RED,
                '2': FOREGROUND_GREEN,
                '3': FOREGROUND_RED | FOREGROUND_GREEN,
                '4': FOREGROUND_BLUE,
                '5': FOREGROUND_RED | FOREGROUND_BLUE,
                '6': FOREGROUND_BLUE | FOREGROUND_GREEN,
                '7': FOREGROUND_WHITE,
                }

            for match in _decode_re.finditer(text):
                code = match.group(1)
                if not code:
                    io.write(match.group(0))
                elif code == 'N':
                    cwrite.state = FOREGROUND_WHITE
                    _set_windows_colour(cwrite.state, io)
                elif code == 'U':
                    pass
                elif code == 'B':
                    cwrite.state ^= FOREGROUND_INTENSITY
                    _set_windows_colour(cwrite.state, io)
                elif code >= '0' and code <= '7':
                    cwrite.state &= ~FOREGROUND_WHITE
                    cwrite.state |= colour_map[code]
                    _set_windows_colour(cwrite.state, io)
                else:
                    raise NotImplementedError('Unsupported colour code %s' %
                        match.group(0))

        cwrite.state = FOREGROUND_WHITE
    except ImportError:
        def _set_windows_colour(colour, fd=None):
            return False

elif _stdout_is_a_tty:
    _terminal_type = 'ansi'
    try:
        import curses
        import signal

        curses.setupterm()
        _terminal_colours = curses.tigetnum('colors')

        # Reconfigure curses on window resize
        def sigwinch_handler(n, frame):
            curses.setupterm()

        signal.signal(signal.SIGWINCH, sigwinch_handler)
    except:
        _terminal_colours = 0

    def getch():
        """Get a single character from the terminal."""
        import tty
        import termios

        fd = sys.stdin.fileno()
        try:
            old_settings = termios.tcgetattr(fd)
        except termios.error:
            return os.read(fd, 1)
        try:
            tty.setraw(fd)
            ch = os.read(fd, 1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch


    def cwrite(io, text):
        io.write(_decode(text)[0])
else:
    _terminal_type = 'dumb'

    def getch():
        return sys.stdin.read(1)


    cwrite = mono_cwrite


cwrite.__doc__ = \
    """Print using simple colour escape codes.

    Colour is not automatically reset at the end of output.

    If ``sys.stdout`` is not a TTY, colour codes will be stripped.
    """


class _Codec(codecs.Codec):
    def __init__(self, *args, **kwargs):
        try:
            codecs.Codec.__init__(self, *args, **kwargs)
        except AttributeError:
            pass
        self.reset()

    _encode_mapping = {
        0: '^N', 1: '^B', 4: '^U', 22: '^B', 24: '^U', 30: '^0', 31: '^1',
        32: '^2', 33: '^3', 34: '^4', 35: '^5', 36: '^6', 37: '^7',
    }

    def decode(self, input, errors='strict'):
        return _decode_re.sub(self._decode_match, input)

    def encode(self, input, errors='strict'):
        return _encode_re.sub(self._encode_match, input)

    def reset(self):
        self.bold = False
        self.underline = False

    # Internal methods
    def _encode_match(self, match):
        c = match.group(1)
        if c:
            return self._encode_mapping[int(c)]
        return match.group(0)

    def _decode_match(self, match):
        c = match.group(1)
        if c:
            if c == 'B':
                self.bold = not self.bold
                if self.bold:
                    return "\033[1m"
                else:
                    return "\033[22m"
            elif c == 'U':
                self.underline = not self.underline
                if self.underline:
                    return "\033[4m"
                else:
                    return "\033[24m"
            elif c == 'N':
                self.underline = self.bold = 0
                return "\033[0m"
            elif c >= '0' and c <= '7':
                return "\033[3" + c + "m"
            else:
                return match.group(0)
        return match.group(0)


class _CodecStreamWriter(_Codec, codecs.StreamWriter):
    def __init__(self, stream, errors='strict'):
        _Codec.__init__(self)
        codecs.StreamWriter.__init__(self, stream, errors)
        self.errors = errors

    def write(self, object):
        self.stream.write(self.decode(object))

    def writelines(self, lines):
        for line in lines:
            self.write(line)
            self.write('\n')


class _CodecStreamReader(_Codec, codecs.StreamReader):
    def __init__(self, stream, errors='strict'):
        _Codec.__init__(self)
        codecs.StreamReader.__init__(self, stream, errors)

    def read(self, size=-1, chars=-1):
        raise NotImplementedError

    def readline(self, size=None, keepends=True):
        raise NotImplementedError

    def readlines(self, sizehint=None, keepends=True):
        raise NotImplementedError

    def seek(self, offset, whence=0):
        self.stream(offset, whence)
        self.reset()


def _decode(input, errors='strict'):
    return (_Codec(errors=errors).decode(input), len(input))


def _encode(input, errors='strict'):
    return (_Codec(errors=errors).encode(input), len(input))


def register_codec():
    """Register the 'cly' codec with Python.

    The formatting syntax can then be used like any other codec:

    >>> register_codec()
    >>> '^Bbold^B'.decode('cly')
    '\\x1b[1mbold\\x1b[22m'
    >>> '\\x1b[1mbold\\x1b[22m'.encode('cly')
    '^Bbold^B'
    """
    def inner_register(encoding):
        if encoding != 'cly':
            return None
        return (_encode, _decode, _CodecStreamReader, _CodecStreamWriter)
    return codecs.register(inner_register)


def cencode(text):
    """Encode to CLY colour-encoded text."""
    return _encode(text)[0]


def cdecode(text):
    """Decode CLY colour-encoded text.

    Use this to convert '^Bfoo^N' to the ANSI equivalent.
    """
    return _decode(text)[0]


def cprint(*args):
    """Emulate the ``print`` builtin, with terminal shortcuts."""
    if args and type(args[0]) is file:
        stream = args[0]
        args = args[1:]
    else:
        stream = sys.stdout
    cwrite(stream, ' '.join(map(str, args)) + '\n')


def cstrip(text):
    """Strip colour codes from text."""
    return _cstrip_re.sub('', text)


def clen(arg):
    """Return the length of arg after colour codes are stripped."""
    return len(cstrip(arg))


def cerror(*args):
    """Print a message in red to stderr."""
    cprint(sys.stderr, "^1^B" + ' '.join(map(str, args)) + '^N')


def cfatal(*args):
    """Print a message in red to stderr then exit with status -1."""
    cprint(sys.stderr, "^1^B" + ' '.join(map(str, args)) + '^N')
    sys.exit(-1)


def cwarning(*args):
    """Print a yellow warning message to stderr."""
    cprint(sys.stderr, "^3^B" + ' '.join(map(str, args)) + '^N')


def cinfo(*args):
    """Print a green notice."""
    cprint("^2" + ' '.join(map(str, args)) + '^N')


def termwidth():
    """Guess the current terminal width.

    Returns -1 if the terminal width can not be determined.
    """
    if not _stdout_is_a_tty:
        return -1
    try:
        import curses
        return curses.tigetnum('cols')
    except:
        return int(os.environ.get('COLUMNS', -1))


def termheight():
    """Guess the current terminal height.

    Returns -1 if the terminal height can not be determined.
    """
    if not _stdout_is_a_tty:
        return -1
    try:
        import curses
        return curses.tigetnum('lines')
    except:
        return int(os.environ.get('LINES', -1))


def csplice(text, start=0, end=-1):
    """Splice a colour encoded string."""
    out = ''
    if end == -1:
        end = len(text)
    sofar = 0
    for token in _decode_re.finditer(text):
        if sofar > end: break
        txt = token.group(0)
        if token.group(1):
            if start < sofar < end:
                out += txt
        else:
            # Whether beginning and end of segment are in slice
            bs = start < sofar < end
            es = start < sofar + len(txt) < end
            if bs and es:
                out += txt
            elif not bs and es:
                out += txt[start - sofar:]
            elif bs and not es:
                out += txt[:end - sofar]
                break
            elif sofar <= start and sofar + len(txt) >= end:
                out += txt[start - sofar:end]
                break
            sofar += len(txt)
    return out


def cwraptext(rtext, width=None, subsequent_indent=''):
    """Wrap multi-line text to width (defaults to :func:`termwidth`)"""
    if width is None:
        width = termwidth()
        if width == -1:
            return [rtext]
    out = []
    for text in rtext.splitlines():
        tokens = [t.group(0) for t in _cwrap_re.finditer(text)] + [' ' * width]
        line = tokens.pop(0)
        first_line = 1

        def add_line(line, first_line):
            if clen(line.rstrip()) > width:
                tokens.insert(0, csplice(line, width))
                line = csplice(line, 0, width)
            out.append((not first_line and subsequent_indent or '') + line.rstrip())
            first_line = 0
            if not out[-1]:
                out.pop()
            return first_line

        if tokens:
            while tokens:
                if clen(line) + clen(tokens[0].rstrip()) > width:
                    first_line = add_line(line, first_line)
                    line = tokens.pop(0)
                else:
                    line += tokens.pop(0)
            if line:
                add_line(line, first_line)
        else:
            out.append('')
    return out


def wraptoterm(text, **kwargs):
    """Wrap the given text to the current terminal width"""
    return '\n'.join(cwraptext(text, **kwargs))


def rjustify(text, width=None):
    """Right justify the given text."""
    if width is None:
        width = termwidth()
        if width == -1:
            return text
    text = cwraptext(text, width)
    out = ''
    for line in text:
        out += (' ' * (width - clen(line))) + line + '\n'
    return out.rstrip()


def cjustify(text, width=None):
    """Centre the given text."""
    if width is None:
        width = termwidth()
        if width == -1:
            return text
    text = cwraptext(text, width)
    out = ''
    for line in text:
        out += (' ' * ((width - clen(line)) / 2)) + line + '\n'
    return out.rstrip()


def print_table(header, table, sep=u' ', indent=u'', expand_to_fit=True,
                header_format='^B^U', row_format=('^6', '^B^6'),
                min_widths=None, term_width=None):
    """Print a list of lists as a table, so that columns line up nicely.

    :param header: List of column headings. Will be printed as the first row.
    :param table: List of lists for the table body.
    :param sep: The column separator.
    :param indent: Table indentation as a string.
    :param header_format: Formatting to use for header.
    :param row_format: A tuple specifying cycling formatting colours to use for
                       each row.
    :param expand_to_fit: If a boolean, signifies whether print_table should
                          expand the table to the width of the terminal or
                          compact it as much as possible. If an integer,
                          specifies the width to expand to.
    :param min_widths: Columns will be guaranteed to be at least the width of
                       each element in this list. May also be a dictionary of
                       column indices to widths.
    :param term_width: Override terminal width detection.

    :returns: List of strings, one per line.

    Note: In addition to the normal formatting codes supported by :func:`cprint`,
    :func:`print_table` supports the ``^R`` formatting code, which corresponds
    to the colour formatting of the current table row.
    """
    def ctlen(s):
        return clen(s.replace('^R', ''))

    seplen = len(sep)
    # Normalise rows
    rows = [map(unicode, r) for r in [list(header)] + list(table)]
    columns = len(rows[0])

    # Scale size_hints percentages to terminal width
    if term_width is None:
        term_width = termwidth()
        if term_width == -1:
            term_width = max([sum(map(ctlen, r)) + len(r) for r in rows])
            min_widths = reduce(lambda a, b: map(max, zip(a, b)),
                                [map(lambda c: ctlen(c) + 1, r) for r in rows])
        else:
            term_width = term_width - (columns - 1) * seplen - ctlen(indent)
    if not isinstance(min_widths, dict):
        min_widths = dict(enumerate(min_widths or []))

    # Column widths
    avg_width = float(term_width) / columns
    # Use the mid-point between the maximum word width and the maximum length
    # of the column.
    widths = [(max([ctlen(w) for cell in column for w in cell.split()])
               + max(map(ctlen, column))) / 2 + seplen
              for column in zip(*rows)]
    #widths = [int(min(c, avg_width)) for c in widths]
    # Apply user-specified column widths.
    widths = [max(c, min_widths.get(i, 1)) for i, c in enumerate(widths)]
    width = sum(widths)

    # Scale columns to fit
    if width > term_width or expand_to_fit:
        scale = float(term_width - sum(min_widths.values())) / width
        widths = [max(int(w * scale), min_widths.get(i, 1))
                  for i, w in enumerate(widths)]

    row_alt = -1
    for row in rows:
        # Cycle through row formats
        if row_alt == -1:
            format = header_format
        else:
            format = row_format[row_alt % len(row_format)]
        row_alt += 1

        wrapped = [cwraptext(c.replace('^R', format), widths[i])
                   for i, c in enumerate(row)]
        maxrows = max([0] + map(len, wrapped))
        for col in wrapped:
            col += [''] * (maxrows - len(col))

        prefix = indent + format
        for y in range(len(wrapped[0])):
            cwrite(sys.stdout, prefix)
            for x, cell in enumerate(wrapped):
                cwrite(sys.stdout, cell[y].ljust(widths[x]))
                if x < columns - 1:
                    cwrite(sys.stdout, ' ')
                else:
                    cwrite(sys.stdout, '\n')
            cwrite(sys.stdout, '^N')


if __name__ == '__main__':
    import doctest
    doctest.testmod()
