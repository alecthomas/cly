# -*- coding: utf-8 -*-
#
# Copyright (C) 2006-2008 Alec Thomas <alec@swapoff.org>
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution.
#

"""CLY parser classes.

Constructs for parsing user input with a :class:`~cly.builder.Grammar`.
"""


__all__ = ['HelpParser', 'Context', 'Parser']
__docformat__ = 'restructuredtext en'


from cly.exceptions import *


class HelpParser(object):
    """Extract the help for children of the specified Node.

    Help is extracted from the Node's children, following branches, and
    returned ordered by group, order and finally help key and string.
    """
    def __init__(self, context, node):
        self.help = []
        self.node = node

        def parse_help(node):
            help = node.help(context)
            if isinstance(help, basestring):
                if node.name == node.pattern:
                    return [(node.name, help)]
                else:
                    return [('<%s>' % node.name, help)]
            else:
                return help

        def add_help(node):
            node_help = sorted(parse_help(node))
            for help in node_help:
                self.help.append((node.group, node.order, help[0], help[1]))

        for child in node.children(context, follow=True):
            if child.visible(context):
                add_help(child)

        self.help.sort()

    def __iter__(self):
        """Iterate over each (order, key, help) help tuple.

        >>> from cly.builder import Grammar, Node, Help
        >>> context = Context(None, None)
        >>> class Test(Node):
        ...   def help(self, context):
        ...     return 'HELP!'
        >>> help = HelpParser(context, Grammar(
        ...     one=Node(help='1'),
        ...     two=Node(help=Help.pair('<two>', '2'), group=2),
        ...     three=Test(help='HELP!'),
        ...     ))
        >>> list(help)
        [(0, 'one', '1'), (0, 'three', 'HELP!'), (2, '<two>', '2')]
        """

        for help in self.help:
            yield (help[0],) + help[2:]

    def format(self):
        """Format help into a human readable form.

        Output is formatted for use with ``cly.console``.

        Returns a list of lines of text.

        >>> from cly.builder import Grammar, Node, Help
        >>> import sys
        >>> context = Context(None, None)
        >>> grammar = Grammar(
        ...     one=Node(help='1'),
        ...     two=Node(help=Help.pair('<two>', '2'), group=2))
        >>> help = HelpParser(context, grammar)
        >>> print '\\n'.join(help.format())
          ^Bone  ^B 1
        <BLANKLINE>
          ^B<two>^B 2
        """
        if not self.help:
            return []
        last_group = None
        max_len = max([len(h[2]) for h in self.help])
        out = []
        for group, order, command, help in self.help:
            if last_group is not None and last_group != group:
                out.append('')
            last_group = group
            out.append('  ^B%-*s^B %s' % (max_len, command, help))
        return out


class Context(object):
    """Represents the parsing context for a single command.

    A `Context` is created automatically when input is parsed. It contains all
    the information needed to maintain state during the parse, including the
    current cursor position in the input stream, the current node in the
    grammar, variables collected and a history of nodes traversed.

    Basic usage is::

      parser = Parser(grammar)
      context = parser.parse('some input text')
      print context.vars

    If the input is invalid the context will have consumed as much input as
    possible. The attributes ``parsed`` and ``remaining`` contain how much text has
    been consumed and remains, respectively.

    Useful attributes:

    .. attribute:: parser

        :class:`Parser` this `Context` is attached to.

    .. attribute:: command

        Command being parsed.

    .. attribute:: cursor

        Position of :class:`Parser` cursor.

    .. attribute:: vars

        :class:`~cly.builder.Variable`\ s collected during the parse.

    """
    def __init__(self, parser, command, data=None):
        self.parser = parser
        self.command = command
        self.cursor = 0
        self.data = data
        self.vars = {}
        self._traversed = {}
        self.trail = []

    def _get_remaining_input(self):
        """Return the current remaining unparsed text in the command.

        >>> context = Context(None, 'one two')
        >>> context.advance(4)
        >>> context.remaining
        'two'
        """
        return self.command[self.cursor:]
    remaining = property(_get_remaining_input, doc=_get_remaining_input.__doc__)

    def _get_parsed(self):
        """Return command text that has been successfully parsed.

        >>> context = Context(None, 'one two')
        >>> context.advance(4)
        >>> context.parsed
        'one '
        """
        return self.command[:self.cursor]
    parsed = property(_get_parsed, doc=_get_parsed.__doc__)

    def _last_node(self):
        """Return the last node parsed.

        >>> from cly.builder import Grammar, Node
        >>> parser = Parser(Grammar(one=Node(two=Node())))
        >>> context = parser.parse('one two three')
        >>> context.last_node
        <Node:/one/two>
        """
        if self.trail[-1][1] is None or self.trail[-1][1].group():
            return self.trail[-1][0]
        else:
            return self.trail[-2][0]
    last_node = property(_last_node, doc=_last_node.__doc__)

    def execute(self):
        """Execute the current (terminal) node. If there is still input
        remaining an exception will be thrown.

        >>> from cly.builder import Grammar, Node, Action
        >>> def test(): print 'OK'
        >>> parser = Parser(Grammar(one=Node()(Action(callback=test))))
        >>> context = parser.parse('one')
        >>> context.execute()
        OK
        """
        if self.remaining.strip():
            raise InvalidToken(self)
        node = self.trail[-1][0]
        return node.terminal(self)

    def advance(self, distance):
        """Advance cursor.

        >>> context = Context(None, 'one two')
        >>> context.cursor
        0
        >>> context.advance(4)
        >>> context.cursor
        4
        """
        self.cursor += distance

    def candidates(self, text=None):
        """Return potential candidates from children of last successfully
        parsed node.

        Arguments:
            :text: If provided, return candidates after ``text``, otherwise the
                   remaining unparsed text in the current command will be used.

        >>> from cly.builder import Grammar, Node
        >>> parser = Parser(Grammar(one=Node()(two=Node(),
        ...                 three=Node()), four=Node()))
        >>> context = parser.parse('one')
        >>> list(context.candidates())
        ['three ', 'two ']
        >>> list(context.candidates('th'))
        ['three ']
        """
        if text is None:
            text = self.remaining
        for child in self.last_node.children(self, follow=True):
            for candidate in child.candidates(self, text):
                yield candidate

    def help(self):
        """Return a HelpParser object describing the last successfully parsed
        node.

        >>> import sys
        >>> from cly.builder import Grammar, Node
        >>> parser = Parser(Grammar(one=Node(help='4', two=Node(help='2'),
        ...                 three=Node(help='3')), four=Node(help='4')))
        >>> context = parser.parse('one')
        >>> help = context.help()
        >>> print '\\n'.join(help.format())
          ^Bthree^B 3
          ^Btwo  ^B 2
        """
        return HelpParser(self, self.last_node)

    def selected(self, node):
        """The given node has been selected and will be followed."""
        path = node.path()
        self._traversed.setdefault(path, 0)
        self._traversed[path] += 1

    def traversed(self, node):
        """How many times has node been traversed in this context?

        >>> from cly.builder import Grammar, Node, Alias
        >>> parser = Parser(Grammar(one=Node(traversals=0)(Alias(target='/one'))))
        >>> node = parser.find('/one')
        >>> for i in range(4):
        ...     context = parser.parse('one ' * i)
        ...     print context.traversed(node), context.parsed # doctest: +NORMALIZE_WHITESPACE
        0
        1 one 
        2 one one 
        3 one one one 
        """
        return self._traversed.get(node.path(), 0)

    def update_locals(self, locals):
        """Update locals before XML evaluation."""
        return locals

    def __repr__(self):
        return "<Context command:'%s' remaining:'%s'>" % (self.command, self.remaining)


class Parser(object):
    """Parse and execute user input against a :class:`~cly.builder.Grammar`.

    For each parse, the parser creates a :class:`Context` containing the state
    for the run and parses the input, and executes any callbacks.

    After parsing, the returned :class:`Context` can be interrogated for
    information or used to execute any :class:`~cly.builder.Action`\ s.

    Arguments:
        :grammar: Grammar to parse with.
        :data: User data to attach to Context.
        :context_factory: A callable used to create new :class:`Context`
                          objects.
    """
    def __init__(self, grammar, data=None, context_factory=Context):
        """Construct a new Parser."""
        self.grammar = grammar
        self.data = data
        self.labels = self._collect_labels()
        self.context_factory = context_factory

    def _set_grammar(self, grammar):
        """Set grammar to parse with."""
        from cly.builder import Grammar
        assert isinstance(grammar, Grammar)
        self._grammar = grammar

    def _get_grammar(self):
        """The :class:`~cly.builder.Grammar` associated with this parser."""
        return self._grammar

    grammar = property(_get_grammar, _set_grammar)

    def parse(self, command, data=None):
        """Parse command using the current :class:`~cly.builder.Grammar`.

        This will return a :class:`Context` object that can be used to inspect
        the state of the parser.

        Arguments:
            :command: String to parse.
            :data: Used to pass user data through to callbacks. The
                   :class:`Context` object has this as an attribute , available
                   to any :class:`~cly.builder.Action` node callbacks that have
                   set ``with_context=True``.

        >>> from cly import *
        >>> parser = Parser(Grammar(one=Node(), two=Node(three=Node(
        ...                 action=Action(callback=lambda: "foo bar")))))
        >>> context = parser.parse('two three')
        >>> context
        <Context command:'two three' remaining:''>
        >>> context.execute()
        'foo bar'
        >>> parser.parse('two four')
        <Context command:'two four' remaining:'four'>
        """
        if data is None:
            data = self.data
        context = self.context_factory(self, command, data)

        def parse(node, match):
            context.trail.append((node, match))
            if match is not None:
                node.advance(context)
            node.selected(context, match)

            for subnode in node.next(context):
                if subnode.valid(context):
                    submatch = subnode.match(context)
                    if submatch is not None:
                        return parse(subnode, submatch)
            else:
                return
            raise InvalidToken(context)

        parse(self.grammar, None)
        return context

    def merge(self, grammar, where=None):
        """Merge another grammar into this one.

        Arguments:
            :where: A label or path to a node.
            :grammar: Grammar to merge.
        """
        if where is None:
            assert hasattr(grammar, 'graft'), \
                'need either an explicit "where" or a "graft" attribute on ' \
                'the <grammar> root'
            where = grammar.graft
        where = self.find(where)
        where.update(grammar)
        self.labels.update(self._collect_labels())

    def execute(self, command, data=None):
        """Parse and execute the given command.

        This is a convenience function that calls :meth:`~Context.execute` on
        the :class:`Context` object returned by :meth:`parse`.

        Arguments are the same as for :meth:`parse`.

        >>> from cly.builder import Grammar, Node, Action
        >>> parser = Parser(Grammar(one=Node(), two=Node(three=Node(
        ...                 action=Action(callback=lambda: "foo bar")))))
        >>> parser.execute('two three')
        'foo bar'
        """
        return self.parse(command, data).execute()

    def find(self, path):
        """Find a node by its absolute path.

        >>> from cly.builder import Grammar, Node, Action
        >>> parser = Parser(Grammar(one=Node(), two=Node(three=Node())))
        >>> parser.find('/two/three')
        <Node:/two/three>
        """
        return self.grammar.find(path)

    def _collect_labels(self):
        """Collect labels from grammar."""
        labels = {}
        for node in self.grammar.walk():
            if node.label is not None:
                labels[node.label] = node
        return labels


if __name__ == '__main__':
    import doctest
    doctest.testmod()
