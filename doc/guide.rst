CLY Developer's Guide
=====================

.. contents::

Overview
--------

CLY provides a convenient means to easily build command-line interfaces. This
is achieved by defining a CLY grammar in either XML or Python then
constructing a CLY parser object from the grammar. The parser parses user
input against the grammar, executes actions, provides completion, and so on.

A built-in terminal interface based on readline is provided.

Experimenting
-------------

The quickest way to experiment with CLY is by passing a :class:`~cly.builder.Grammar` or
:class:`~cly.parser.Parser` object to the :func:`~cly.interactive.interact` function:

.. code-block:: python

  from cly import interact

  interact(grammar_or_parser)

This will start a readline console using the given grammar. Press ``?`` at any
time for contextual help, ``<Tab>`` to attempt completion, and ``<Ctrl-D>``
(EOF) on an empty line to terminate the shell.

Now, on with the nitty gritty.

Building a Grammar from Python
------------------------------

Matching Input
~~~~~~~~~~~~~~

The syntax of a shell is defined as a tree of :class:`~cly.builder.Node` objects.  Each node
matches a token of user input defined by the ``pattern`` attribute of the
:class:`~cly.builder.Node` and defaults to the :class:`~cly.builder.Node` name. ``pattern`` is treated as a
regular expression. For example, the following grammar would match the token
``one``:

.. code-block:: python

  grammar = Grammar(
    one=Node()
  )

Because nodes are hierarchical, child nodes are only considered for
matching after the parent has matched and consumed a token. The
following grammar would match the tokens ``parent child``:

.. code-block:: python

  grammar = Grammar(
    parent=Node()(
      child=Node()
    )
  )

As mentioned, the name of the node is used as the default pattern to
match against input tokens. This can be overridden by passing
``pattern=<regex>`` to the constructor. The following example will match
one or more digits:

.. code-block:: python

  grammar = Grammar(
    number=Node(pattern=r'\d+'),
  )


Grammar Branching
~~~~~~~~~~~~~~~~~

It's a common requirement that paths in the grammar be executed
multiple times, whether that be to enter a list of IP addresses, allow
multiple commands at a branch, etc. In CLY this is achieved with the
:class:`~cly.builder.Alias` node. An alias node, as its name suggests, aliases its target
at the current location, effectively merging two branches of the
grammar.

Here's an example:

.. code-block:: python

  grammar = Grammar(
    one=Node(
      Alias(target='/three'),
      two=Node(),
    ),
    three=Node(),
  )

This will alias the node ``/three`` underneath ``/one``. That is, this
grammar will match the input ``one three``.

Nodes are referenced by their full or relative path, and globs may be
used to alias multiple nodes at once. The following example will alias
everything at ``/three/*``, underneath ``/one/``:

.. code-block:: python

  grammar = Grammar(
    one=Node(
      Alias(target='../../three/*'),
      two=Node(),
    ),
    three=Node(
      four=Node(),
      five=Node(),
    ),
  )

By default, nodes may only be traversed once per parse run. This can be
overridden by passing ``traversals=<count>`` to node constructors. If
``traversals == 0`` then there are no limits set. If ``traversals > 1``
then *the variable will be stored as a list*.

Collecting Variables
~~~~~~~~~~~~~~~~~~~~

Matching input is great, but if you want your grammar to be useful
you're going to want it to do something with it. This is where the
:class:`~cly.builder.Variable` class comes in: it stores matching input tokens into the
parse context for later use as arguments to execution callbacks.

Here's an example of a variable matching a number:

.. code-block:: python

  grammar = Grammar(
    number=Variable(pattern=r'\d+'),
  )

The matched input token is stored by the ``Variable.selected()`` method,
into the ``vars`` dictionary of the context.

When parsing terminates on an action, the context variables are passed
as keyword arguments to the final callback. For example, given the input
``1234`` the above grammar would execute the callback with
``callback(number='1234')``

It's as simple as that.

Variable Types
~~~~~~~~~~~~~~

By default, variables are passed to callbacks as strings. Having to then
manually convert these arguments to whatever type you want would be
tedious, so CLY allows end users to customise the value passed to the
callback by subclassing :class:`~cly.builder.Variable` and overriding the ``parse()``
method. The default behaviour for this method is to pass all matching
input text as a string.

Continuing the example from the previous section:

.. code-block:: python

  class Number(Variable):

    pattern = r'\d+'

    def parse(self, context, match):
      return int(match.group())

Where ``context`` is a ``cly.parser.Context`` object and ``match`` is a
``re.Match`` object.

Now our callback will be executed with ``callback(number=1234)``. Of
course, much more complex conversions can occur, including IP address
parsing, E-Mail parsing, etc. A set of commonly used variable types is
included in ``cly.builder``.

Note how the ``pattern`` attribute may be a class member as a convenience. 

Executing Callbacks
~~~~~~~~~~~~~~~~~~~

Now that we have collected variables from the user into our context, we
want to execute a callback with those variables. This is achieved with
the :class:`~cly.builder.Action` node and matches the end of input.

Here's an example:

.. code-block:: python

  def print_number(number):
    print number

  grammar = Grammar(
    number=Number(
      Action(callback=print_number),
    )
  )

In addition to all of the attributes included with :class:`~cly.builder.Node`,
:class:`~cly.builder.Action` also has the ``with_context`` flag. This can be
used to pass the current parser :class:`~cly.parser.Context` to the callback as
the first argument. Refer to `Passing Context Objects to Callbacks`_ for
more information about user contexts.

Implementing Custom Completion
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To implement your own custom completion, override ``Node.candidates(context,
text)``. This can be achieved by passing ``candidates=<callable>`` to the
:class:`~cly.builder.Node` constructor or by normal subclassing.

The `canidates()` method itself must return a list of strings *with trailing
whitespace* that match the ``text`` argument. ``context`` is a parser context
object, described elsewhere.

Here's an example of how one could implement a kill command:

.. code-block:: python

  import os
  import signal
  from cly import *

  # Build dictionary of signal_name:signal
  signals = dict([(s[3:], getattr(signal, s))
                  for s in dir(signal)
                  if s.startswith('SIG')
                     and not s.startswith('SIG_')])

  def complete_signals(context, text):
    return [s + ' ' for s in signals.keys() if s.startswith(text)]

  def kill(pid, signal=None):
    try:
      os.kill(pid, signals.get(signal, signals['TERM']))
    except OSError, e:
      print 'error:', e

  grammar = Grammar(
    kill=Node(
      pid=Integer(help='Process ID')(
        action=Action(callback=kill, help='Send signal'),
        signal=Variable(help='Signal to send to process',
                        candidates=complete_signals,
                        match_candidates=True)(
            Alias(target='/kill/pid/action'),
          ),
        ),
      ),
    )

  interact(grammar)
  

Adding Help
~~~~~~~~~~~

Help is optional but recommended. Add help to a node with the keyword argument
``help`` which must either be a help string, or a callable that returns an
iterable of ``(key, help)`` tuples. This is used to construct contextual help
when a user presses ``?``.

In the vast majority of cases a simple string, or possibly a pair, will be sufficient.
For when it is not, the convenience class ``cly.parser.Help`` is available to
construct help, either from a single pair:

.. code-block:: python

  one=Node(help=Help.pair('one', 'Command 1'))

or from a list of tuples:

.. code-block:: python

  help = [('one', 'Command 1'),
          ('1', 'Command 1')]

  one=Node(help=Help(help), pattern=r'one|1')

Types of Nodes
~~~~~~~~~~~~~~
CLY includes a whole suite of builtin node types, which can be broken down into
the following groups:

:class:`~cly.builder.Node`
    The base grammar node. These nodes in the grammar are purely for
    routing the grammar to other nodes. They have no side-effects.

:class:`~cly.builder.Grammar`
    The root of the grammar. Contains all other nodes and acts purely as a
    container and a match for the beginning of input.

:class:`~cly.builder.Group`
    A convenience class used to apply attributes to a group of nodes.

:class:`~cly.builder.Alias`
    Allow branches of the grammar to be included in other locations. The only
    argument to :class:`~cly.builder.Alias` is the relative or absolute path of the branch to be
    included. This path can take the form of a glob in order to include
    multiple nodes. Use this to create optional arguments.

:class:`~cly.builder.Variable`
    Variable nodes insert their matching input into the ``vars`` dictionary of
    the :class:`~cly.parser.Context`, after being parsed by the
    :meth:`~cly.parser.Parser.parse()` method. If the
    :class:`~cly.builder.Variable` attribute ``traversals`` is not 1, values are
    collected into a list rather than a scalar.  CLY includes a number of
    potentially useful :class:`~cly.builder.Variable` subclasses such as
    :class:`~cly.builder.URI`, :class:`~cly.builder.Integer`,
    :class:`~cly.builder.Float`, etc.

:class:`~cly.builder.Action`
    An action matches the end of a line and is used to execute a callback. It
    passes any ``vars`` parsed by previous :class:`~cly.builder.Variable` nodes through to the
    callback as arguments.

Full details are available in the :ref:`api`.

Node Attributes and Constructor Arguments
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Each node has a set of attributes that define its behaviour, from the regular
expression used to match input, through to the number of times the node can
be traversed in a parse context.

These attributes can be set in four ways:

By passing keyword arguments to the constructor:

.. code-block:: python

  Node('Help', pattern=r'.+')

By "calling" the node with keyword arguments:

.. code-block:: python

  Node('Help')(pattern=r'.+')

With the special :class:`~cly.builder.Group` node. This node will set attributes on *all*
descendants:

.. code-block:: python

  Group(traversals=0)(
    one=Node(),
    two=Node(),
  )


By subclassing the node and defining the attribute as a class attribute:

.. code-block:: python

  class Any(Node):
    pattern = r'.+'

For details on what attributes are available for each node class, refer to the
:ref:`api`.

Context
~~~~~~~
Each command is parsed within a context. The context stores state information
such as variables collected, number of traversals of nodes, cursor location,
etc. It is most useful when overriding default :class:`~cly.builder.Node` behaviour, where
the ``vars`` data member may be inspected for variables that have
already been collected.

Defining a Grammar in XML
-------------------------
CLY XML grammars are simply a one-to-one mapping of XML elements to Python
:class:`~cly.builder.Node` objects. Attributes of each element are passed as arguments
to the :class:`~cly.builder.Node` constructor.

Here's a simple example of a grammar defining a single "echo" command:

.. code-block:: xml

  <?xml version="1.0"?>
  <grammar xmlns="http://swapoff.org/cly/xml">
    <node name="echo">
      <variable name="text" pattern=".+">
        <action callback="echo(text)"/>
      </variable>
    </node>
  </grammar>

Parsing an XML Grammar
~~~~~~~~~~~~~~~~~~~~~~

The :class:`~cly.builder.XMLGrammar` class accepts a file-like object or a filename as the first
argument and builds a new :class:`~cly.grammar.Grammar` object from that XML. An optional second
argument ``extra_nodes`` can be used to pass a list of extra :class:`~cly.builder.Node`
sub-classes to recognise as elements. 

Here's an example that uses the previously defined XML grammar to implement an
"echo" command:

.. code-block:: python

  from cly import Grammar, interact

  def echo(text):
      print text

  grammar = XMLGrammar('example.xml')
  interact(grammar, data={'echo': echo})

We can then modify just the XML and get a slightly more complex example with
looping and grouping:

.. code-block:: xml

  <?xml version="1.0"?>
  <grammar xmlns="http://swapoff.org/cly/xml">
    <node name="echo">
      <apply traversals="0">
        <variable name="text">
          <alias target="/echo/*"/>
          <action callback="echo(text)"/>
        </variable>
      </apply>
    </node>
  </grammar>

The Python code does not change.

XML Attribute Type Conversion
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
All :class:`~cly.builder.Node` constructor arguments that are not strings but are known to the
:class:`~cly.parser.Parser` will be evaluated as Python code, meaning integer arguments will be
converted to integers, callback arguments may contain lambdas, etc.

In this example ``traversals`` will be converted to an integer and passed to the
:class:`~cly.builder.Node` constructor:

.. code-block:: xml

  <?xml version="1.0"?>
  <grammar>
    <node traversals="0">
    ...
    </node>
  </grammar>

Extra attribute conversions can be provided to the :class:`~cly.builder.XMLGrammar` by passing 
a dictionary of attribute names to type conversion functions, as the
``attr_type_map`` keyword argument.

Parsing
-------

A grammar is simply a data structure. To actually utilise it one needs to bind
it to a :class:`~cly.parser.Parser` object and parse some input with it. The parser takes care
of creating a :class:`~cly.parser.Context` for each parse run, parsing the input, and executing
any callbacks.

Parse Context
~~~~~~~~~~~~~
A parse context is created automatically when input is parsed. It contains all
the information needed to parse input tokens, including the current cursor
position in the input stream, the current node in the grammar, variables
collected and a history of nodes traversed.

Basic usage is:

.. code-block:: python

  parser = Parser(grammar)
  context = parser.parse('some input text')
  print context.vars

If the input is invalid the context will have consumed as much input as
possible. The attributes ``parsed`` and ``remaining`` contain how much text has
been consumed and remains, respectively. The context has a number of additional
attributes and methods that are useful to both :class:`~cly.builder.Node` implementations and
:class:`~cly.parser.Parser` users. These are documented in detail in the API documentation.

Passing Context Objects to Callbacks
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Specifying ``with_context=True`` on an Action node causes the active parse
:class:`~cly.builder.Context` to be passed to the action callback as the first
argument. 

.. code-block:: python

  from cly import *

  def echo(context):
    print context

  grammar = Grammar(one=Node(Action(with_context=True, callback=echo)))

  my_context = 'hi'
  parser = Parser(grammar)
  parser.execute('one')

Will print::

  hi


One way of applying this is by binding all callbacks to methods on a
single *class*, then passing an instance of that class as the context:

.. code-block:: python

  from cly import *

  class A(object):
    def __init__(self, name):
      self.name = name

    def one(self):
      print "One:", self.name

  grammar = Grammar(
    one=Node()(
      Action(callback=A.one),
      ),
  )

  a = A('a')
  b = A('b')

  parser = Parser(grammar, with__context=True)

  parser.execute('one', user_context=a)
  parser.execute('one', user_context=b)

This will output::

  One: a
  One: b
