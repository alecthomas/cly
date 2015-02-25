# -*- coding: utf-8 -*-
#
# Copyright (C) 2006-2007 Alec Thomas <alec@swapoff.org>
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution.
#

"""CLY and readline, together at last.

This module uses readline's line editing and tab completion along with CLY's
grammar parser to provide an interactive command line environment.

It includes support for application specific history files, dynamic prompt,
customisable completion key, interactive help and more.

*Users can press ? at any time to view contextual help.*
"""

import os
import sys
import types
import cly.console as console
from cly.exceptions import Error, ParseError
from cly.builder import Grammar
from cly.parser import Parser

try:
    import readline
except ImportError:
    readline = None
try:
    from cly import _rlext
except ImportError:
    _rlext = None
    try:
        import pyreadline
    except ImportError:
        pyreadline = None


__all__ = ['Interact', 'interact', 'brief_exceptions', 'verbose_exceptions',
           'debug_exceptions']
__docformat__ = 'restructuredtext en'


# Interact.loop exception modifiers
def brief_exceptions(interact, context, completing, e):
    """Display the string  summary for exceptions."""
    if not completing:
        console.cerror(str(e))

def verbose_exceptions(interact, context, completing, e):
    if not completing:
        interact.dump_traceback(e)

def debug_exceptions(interact, context, completing, e):
    interact.dump_traceback(e)


class InputDriver(object):
    """Abstraction for line input.""" 

    def __init__(self, parser, prompt, history_file, history_length):
        self.parser = parser
        self.prompt = prompt
        self.history_file = history_file
        self.history_length = history_length

    def enter(self):
        """Enter the input context."""

    def input(self):
        """Input one line from user and return it."""
        raise NotImplementedError

    def leave(self):
        """Exit the input context."""

    @staticmethod
    def usable():
        """Called to determine whether this driver is usable."""
        raise NotImplementedError

    def _set_prompt(self, prompt):
        self._prompt = prompt

    def _get_prompt(self):
        return self._prompt

    prompt = property(lambda self: self._get_prompt(),
                      lambda self, prompt: self._set_prompt(prompt))


class DumbInput(InputDriver):
    """The horror."""

    def input(self):
        return raw_input(self.prompt)

    @staticmethod
    def usable():
        print >> sys.stderr, \
            'WARNING: Most line editing features are unavailable.'
        return True


class ReadlineDriver(InputDriver):
    """Base class for readline variants."""

    def __init__(self, *args, **kwargs):
        super(ReadlineDriver, self).__init__(*args, **kwargs)
        self._cli_inject_text = ''
        self._completion_candidates = []

    def enter(self):
        try:
            readline.set_history_length(self.history_length)
            readline.read_history_file(self.history_file)
        except:
            pass

        readline.parse_and_bind('tab: complete')
        readline.set_completer_delims(' \t')
        readline.set_completer(self._completion)
        readline.set_startup_hook(self._redraw_input)

        self._bind_help()

    def input(self):
        return raw_input(self.prompt)

    def leave(self):
        try:
            readline.write_history_file(self.history_file)
        except:
            pass

    @staticmethod
    def usable():
        if readline:
            print >> sys.stderr, \
                'WARNING: neither pyreadline nor CLY\'s built-in readline ' \
                'extensions found,\n         contextual help is not ' \
                'available.'
        return readline

    def _bind_help(self):
        pass

    def _force_redisplay(self):
        raise NotImplementedError

    def _get_cursor(self):
        raise NotImplementedError

    def _set_cursor(self, cursor):
        raise NotImplementedError

    cursor = property(lambda s: s._get_cursor(), lambda s, c: s._set_cursor(c))

    def _set_prompt(self, prompt):
        self._prompt = console.cdecode(prompt)

    # Internal methods
    def _completion(self, text, state):
        line = readline.get_line_buffer()[0:readline.get_begidx()]
        ctx = None
        try:
            result = self.parser.parse(line)
            if not state:
                try:
                    self._completion_candidates = list(result.candidates(text))
                except Exception, e:
                    Interact.dump_traceback(e)
                    self._force_redisplay()
                    raise
            if self._completion_candidates:
                return self._completion_candidates.pop()
            return None
        except cly.Error:
            return None

    def _redraw_input(self):
        readline.insert_text(self._cli_inject_text)
        self._cli_inject_text = ''

    def _show_help(self, key, count):
        try:
            command = readline.get_line_buffer()[:self.cursor]
            context = self.parser.parse(command)
            if context.remaining.strip():
                print
                candidates = [help[1] for help in context.help()]
                text = '%s^ invalid token (candidates are %s)' % \
                       (' ' * (context.cursor + len(self.prompt)),
                       ', '.join(candidates))
                console.cerror(text)
                self._force_redisplay()
                return
            help = context.help()
            print
            console.cprint('\n'.join(help.format()))
            self._force_redisplay()
            return 0
        except Exception, e:
            Interact.dump_traceback(e)
            self._force_redisplay()
            return 0


class PyReadlineDriver(ReadlineDriver):
    """The IPython pure-Python pyreadline implementation."""

    @staticmethod
    def usable():
        return pyreadline

    def _bind_help(self):
        def _show_help_proxy(_, __):
            self._show_help(None, None)

        pyreadline.rl.mode.cly_help = types.MethodType(
            _show_help_proxy, pyreadline.rl.mode, pyreadline.Readline
            )
        pyreadline.parse_and_bind('?: cly-help')
        pyreadline.parse_and_bind('Shift-?: cly-help')
        pyreadline.parse_and_bind('F1: cly-help')

    def _force_redisplay(self):
        pyreadline.rl._print_prompt()

    def _get_cursor(self):
        return pyreadline.rl.l_buffer.point

    def _set_cursor(self, cursor):
        pyreadline.rl.l_buffer.point = cursor


class ExtendedReadlineDriver(ReadlineDriver):
    """Use CLY's built-in readline extensions."""

    @staticmethod
    def usable():
        return _rlext

    def _bind_help(self):
        _rlext.bind_key(ord('?'), self._show_help)

    def _force_redisplay(self):
        _rlext.force_redisplay()

    def _get_cursor(self):
        return _rlext.cursor()

    def _set_cursor(self, cursor):
        _rlext.cursor(cursor)


class Interact(object):
    """CLY interaction through readline. Due to readline limitations, only one
    Interact object can be active within an application.

    Arguments:

        :grammar_or_parser: The :class:`~cly.parser.Parser` or
                            :class:`~cly.builder.Grammar` to use for
                            interaction.
        :application: The application name. Used to construct the history file
                      name and prompt, if not provided.
        :prompt: The prompt.
        :data: A user-specified object to pass to the parser. The parser builds
               each parse :class:`~cly.parser.Context` with this object, which
               in turn will deliver this object on to terminal nodes that have
               set ``with_context=True``.
        :with_context: Force current parser :class:`~cly.parser.Context` to be
                       passed to all action nodes, unless they explicitly set
                       the member variable ``with_context=False``.
        :history_file: Defaults to ``~/.<application>_history``.
        :history_length: Lines of history to keep.
        :exceptions: See :meth:`loop`.
    """

    # Available input drivers
    INPUT_DRIVERS = [ExtendedReadlineDriver, PyReadlineDriver, ReadlineDriver,
                     DumbInput]


    def __init__(self, grammar_or_parser, application='cly', prompt=None,
                 data=None, history_file=None, history_length=500,
                 exceptions=None):
        if prompt is None:
            prompt = application + '> '
        if history_file is None:
            history_file = os.path.expanduser('~/.%s_history' % application)
        if isinstance(grammar_or_parser, Grammar):
            parser = Parser(grammar_or_parser, data=data)
        else:
            parser = grammar_or_parser
            assert not data, '"data" ignored because a Parser was passed'

        self.parser = parser
        self.exceptions = exceptions or (lambda *a, **kw: True)

        self.input_driver = self.best_input_driver(
            parser, prompt, history_file, history_length
            )

    def once(self):
        """Input one command from the user and return the result of the
        executed command.
        """
        while True:
            command = ''
            try:
                self.input_driver.enter()
                try:
                    command = self.input_driver.input()
                except KeyboardInterrupt:
                    print
                    continue
                except EOFError:
                    print
                    return None
            finally:
                self.input_driver.leave()

            try:
                context = self.parser.parse(command)
                context.execute()
            except ParseError, e:
                self.print_error(context, e)
            return context

    def loop(self, exceptions=None, every=None):
        """Repeatedly read and execute commands from the user.

        Arguments:
            :exceptions: A callback used to handle exceptions. It has the
                         signature:

                         exceptions(interact, context, completing, e) => bool

                         context may be None and completing is True if
                         exception was thrown from a completion function.

                         If True is returned the exception will be re-raised.
            :every: Called with the Interact object before each line is
                    displayed.
        """
        exceptions = exceptions or self.exceptions
        while True:
            try:
                if every:
                    every(self)
                if not self.once():
                    break
            except Exception, e:
                if exceptions(self, None, False, e):
                    raise

    def print_error(self, context, e):
        """Called by `once()` to print a ParseError."""
        candidates = [help[1] for help in context.help()]
        if len(candidates) > 1:
            message = '%s (candidates are %s)'
        else:
            message = '%s (expected %s)'
        message = message % (str(e), ', '.join(candidates))
        self.error_at_cursor(context, message)

    def error_at_cursor(self, context, text):
        """Attempt to intelligently print an error at the current cursor
        offset."""
        text = str(text)
        term_width = console.termwidth()
        indent = ' ' * (context.cursor % term_width
                        + len(self.prompt))
        if len(indent + text) > term_width:
            console.cerror(indent + '^')
            console.cerror(text)
        else:
            console.cerror(indent + '^ ' + text)

    @classmethod
    def dump_traceback(cls, exception):
        import traceback
        from StringIO import StringIO
        out = StringIO()
        traceback.print_exc(file=out)
        print >>sys.stderr, str(exception)
        print >>sys.stderr, out.getvalue()

    def _get_prompt(self):
        return self.input_driver.prompt

    def _set_prompt(self, prompt):
        self.input_driver.prompt = prompt

    prompt = property(_get_prompt, _set_prompt, doc='Prompt. Can be set.')


    @classmethod
    def best_input_driver(cls, *args, **kwargs):
        """Select the "best" available input driver."""
        for driver in cls.INPUT_DRIVERS:
            if driver.usable():
                return driver(*args, **kwargs)
        raise Error('No usable input driver found')


def interact(grammar_or_parser, exceptions=None, *args, **kwargs):
    """Start an interactive session with the given grammar or parser object.

    Arguments are as for :class:`Interact`.
    """
    interact = Interact(grammar_or_parser, *args, **kwargs)
    interact.loop(exceptions=exceptions)
