# -*- coding: utf-8 -*-
#
# Copyright (C) 2006-2007 Alec Thomas <alec@swapoff.org>
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution.
#

"""CLY exception hierarchy."""


import string


__all__ = ['Error', 'InvalidHelp', 'InvalidNodePath', 'InvalidAnonymousNode',
           'ParseError', 'UnexpectedEOL', 'InvalidToken', 'ValidationError',
           'XMLParseError']
__docformat__ = 'restructuredtext en'


class Error(Exception):
    """The base of all CLY exceptions."""


class InvalidHelp(Error):
    """Thrown when the help provided to a Node is of an invalid type."""


class InvalidNodePath(Error):
    """Thrown when an attempt is made to reference an invalid node path. This
    can occur when an Alias target is invalid."""


class InvalidAnonymousNode(Error):
    """When Node is used as a callable to add child nodes, positional arguments
    are treated as anonymous child nodes. This exception is thrown if an object
    that is not a Node is passed."""


class XMLParseError(Error):
    """Report an XML grammar parsing error."""


class ParseError(Error):
    """Report a parse error. Output is formatted using string templates,
    where template variables are passed as arguments to the constructor.

    >>> from cly.parser import Context
    >>> print ParseError(Context(None, 'foo bar'), "remaining=$remaining, time=$time", time=123)
    remaining=foo bar, time=123
    """
    message = 'parse error'

    def __init__(self, context, message=None, **kwargs):
        template = string.Template(message or self.message)
        message = template.safe_substitute(remaining=context.remaining,
                                           **kwargs)
        Error.__init__(self, message)
        self.context = context


class UnexpectedEOL(ParseError):
    """Raised when all input is consumed and no terminal (``Action``) node is
    reached."""
    message = 'more input required'


class InvalidToken(ParseError):
    """Raised when a token is reached that is invalid at the current grammar
    branch."""
    message = "invalid token '$remaining'"


class ValidationError(ParseError):
    """Raised when a variable fails to parse. In practise this is rare, as the
    regex for a variable is usually sufficient to rule it out of selection
    before parsing occurs."""
    message = "validation of '$token' failed; $exception"


if __name__ == '__main__':
    import doctest
    doctest.testmod()
