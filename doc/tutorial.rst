CLY Tutorial
============

.. contents::

Before you start
----------------

As with most things, it is usually better in the long run if you think about 
your design before implementation. With that formality out of the way, the
beauty of CLY, and Python in general, is that it is easy and fun to experiment
with.

For the purposes of this tutorial I will implement a basic "shell", with the
commands ``cat`` and ``quit``. ``cat`` will have full tab completion of files
and directories.

All XML and Python samples in this tutorial are available under
``doc/tutorial/`` in the source distribution.

Finally, following each example using the XML grammar there will be a
manually constructed equivalent. Simply replace:

.. code-block:: python
   
    grammar = XMLGrammar('grammar.xml', ...)

with the corresponding:

.. code-block:: python
   
    grammar = Grammar(grammar, ...)
    

Step One - Fundamentals
-----------------------

The first step is just to import the bare essentials required to get a command 
line interface working. As one of CLY's main goals is to minimize the amount of
code required to implement a command line interface, this is fairly small.

.. code-block:: python

    from cly import *

Step Two - Interaction
----------------------

Making your program interactive is as simple as calling the ``interact()``
function with a grammar:

.. literalinclude:: tutorial/tutorial1.py

This calls ``interact()`` with an empty grammar, which won't do much at this
stage, but will allow interaction.

CLY uses readline for its interactive terminal, so all normal readline options
apply including emacs and vi modes. Command and variable completion can be
triggered by pressing ``<Tab>`` (this can be overridden), pressing ``?`` at any
time will display context-sensitive help, and finally, you can press
``<Ctrl-D>`` to terminate the console interface.

Step Three - And the first *command*-ment shall be ``quit``
-----------------------------------------------------------

The first command we will implement is ``quit``, as it is the most basic.

``tutorial2.py``:

.. literalinclude:: tutorial/tutorial2.py

Here is the XML grammar for this code:

``tutorial2.xml``:

.. literalinclude:: tutorial/tutorial2.xml
   :language: xml

Here's the equivalent manually constructed grammar:

.. code-block:: python

    grammar = Grammar(
        quit=Node(help='Quit')(
            Action(callback=do_quit, help='Quit'),
        ),
    )

**Note:** The apparent redundancy of having two *Quit* nodes is explained
by the behaviour of the ``Action`` node. This node matches the end of the
current command. For example, the following would execute ``quit()`` when an
empty line is passed as the command:

.. code-block:: python

    grammar = Grammar(
        Action(callback=do_quit, help='Quit'),
    )

Which is generally not what one wants.

Step Four - Variables
---------------------

It's all well and good to call a function with no arguments, but you'll often
want to pass user inputted variables along to each ``Action``. This is where 
the ``Variable`` class hierarchy comes in. The class matches user input
and stores the (potentially transformed into another type) value in the ``vars``
dictionary of the current parse ``Context``. When an ``Action`` node is selected it
passes these variables on to its callback as arguments.

``tutorial3.py``:

.. literalinclude:: tutorial/tutorial3.py

Here's the XML grammar:

``tutorial3.xml``:

.. literalinclude:: tutorial/tutorial3.xml
   :language: xml

And finally the manually constructed grammar:

.. code-block:: python

    grammar = Grammar(
        quit=Node(help='Quit')(
            Action(callback=do_quit, help='Quit'),
        ),
        cat=Node('Concatenate files')(
            file=Variable(help='File to concatenate', pattern=r'\S+')(
                Action(callback=do_cat, help='Concatenate files'),
            ),
        ),
    )

Step Five - Recursion
---------------------

This is nice, but what if we want to be able to "cat" multiple files?

``tutorial4.py``:

.. literalinclude:: tutorial/tutorial4.py

The XML grammar:

``tutorial4.xml``:

.. literalinclude:: tutorial/tutorial4.xml
   :language: xml

Each ``Node`` has a ``traversals`` member which specifies the number of times that
node can be traversed in a parse context. This is ``1`` by default, but if we set
this to ``0`` the node may be traversed any number of times.

The second new feature is the ``Alias`` class which, as the name suggests,
makes this node an alias for another node in the grammar tree. The node to
alias is specified as either a relative or absolute path. In this case, the
parent node, whose absolute path is ``/cat/files``.

And again, the manually constructed grammar:

.. code-block:: python

    grammar = Grammar(
        quit=Node(help='Quit')(
            Action(help='Quit', callback=do_quit),
        ),
        cat=Node(help='Concatenate files')(
            files=Variable(help='File to concatenate', pattern=r'\S+', traversals=0)(
                Action(callback=do_cat, help='Concatenate files'),
                Alias(target='..'),
            ),
        ),
    )

Step Six - Completion
---------------------

Variables can have extra intelligence built into them to customise their
behaviour. To make life a bit easier for the end developer a selection of
variables are available in ``cly.builder``. This includes a ``File`` class
which we will use to provide file completion:

``tutorial5.py``:

.. literalinclude:: tutorial/tutorial5.py

Variables can be used to not only validate input, but parse it into a useful
state. By overriding the ``parse()`` method of a ``Variable`` any type can be
inserted into the context. An example of this is the IP variable, which
returns the IP as a tuple of integers.

``tutorial5.xml``:

.. literalinclude:: tutorial/tutorial5.xml
   :language: xml

The manually composed grammar:

.. code-block:: python

    grammar = Grammar(
        quit=Node(help='Quit')(
            Action(help='Quit', callback=do_quit),
        ),
        cat=Node(help='Concatenate files')(
            files=File(help='File to concatenate', traversals=0)(
                Action(callback=do_cat, help='Concatenate files'),
                Alias(target='..'),
            ),
        ),
    )

Conclusion
----------

Hopefully this will have given you a taste of what CLY is capable of. There are quite a
number of other features which allow you to extensively customise the behaviour
of your command line applications.

