# -*- coding: utf-8 -*-
#
# Copyright (C) 2006-2007 Alec Thomas <alec@swapoff.org>
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution.
#

"""CLY is a Python module for simplifying the creation of interactive shells.
Kind of like the builtin `cmd <http://docs.python.org/lib/module-cmd.html>`_
module on steroids.

It has the following features:

  - Automatic tab completion of all commands::

      cly> s<TAB><TAB>
      show status

  - Contextual help::

      cly> <?>
      show    Show information.
      status  Display status summary.

      login   Authenticate.

      quit    Quit.

  - Extensible grammar - define your own commands with full dynamic completion,
    contextual help, and so on.

  - :class:`XML grammar <cly.builder.XMLGrammar>` for building clean MVC style command line interfaces.

  - Simple. Grammars are constructed from objects using a simple *functional*
    style.

  - Multiple grammars can be merged both statically and dynamically.

  - Flexible command grouping and ordering.

  - Grammar parser, including completion and help enumeration, can be used
    independently of the readline-based shell. This allows CLY's parser to
    be used in other environments (think "web-based shell" ;))
"""


__docformat__ = 'restructuredtext en'
__author__ = 'Alec Thomas <alec@swapoff.org>'
try:
    __version__ = __import__('pkg_resources').get_distribution('cly').version
except Exception:
    pass


from cly.parser import *
from cly.builder import *
from cly.interactive import *
