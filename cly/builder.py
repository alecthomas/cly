# -*- coding: utf-8 -*-
#
# Copyright (C) 2006-2007 Alec Thomas <alec@swapoff.org>
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution.
#


"""Classes for constructing CLY grammars."""


import datetime
import os
import posixpath
import re
import warnings
from itertools import chain
from xml.dom import minidom
from inspect import isclass, getargspec
from cly.exceptions import *
from cly.parser import Context, HelpParser

try:
    import pytz
except ImportError:
    pytz = None


__all__ = [
    'Node', 'Masquerade', 'Defaults', 'Alias', 'Group', 'If', 'Apply', 'Action',
    'Variable', 'Grammar', 'XMLGrammar', 'Help', 'LazyHelp', 'Word', 'Keyword',
    'String', 'URI', 'LDAPDN', 'Integer', 'Float', 'IP', 'Hostname', 'Host',
    'EMail', 'File', 'Boolean', 'KeyValue', 'AbsoluteTime', 'RelativeTime',
    'Timezone', 'Base64', 'cull_candidates',
    ]
__docformat__ = 'restructuredtext en'


class Node(object):
    """The base class for all grammar nodes.

    Any :class:`Node` instances passed to the constructor will become children of
    this node in the grammar hierarchy. :class:`Node`\ s as keyword arguments
    will be named after their keyword, while positional arguments will be
    provided auto-generated names. This is generally only useful for "control"
    nodes, such as :class:`Alias`.

    Supported keyword arguments:

        :help:
            string or callable returning a list of (key, help) tuples A help
            string or a callable returning an iterable of (key, help) pairs.
            There is a useful class called Help which can be used for this
            purpose.

        :name:
            The name of the node. If ommitted the keyword argument name used in
            the parent Node is used. The node name also defines the node path
            and the default pattern to match against if not explicitly provided:

            >>> Node(name='something')
            <Node:/something>

    The following constructor arguments are also class variables, and as
    such can be overridden at the class level by subclasses of Node. Useful If
    you find yourself using a particular pattern repeatedly.

        :pattern:
            The regular expression used to match user input. If not provided,
            the node name is used:

            >>> a = Node(name='something')
            >>> a.pattern == a.name
            True

        :separator:
            A regular expression used to match the text separating this node
            and the next.

        :group:
            Nodes with the same group value will be collated visually.
            Generally a number, but can also be a string or any other
            comparable object.

        :order:
            Within a group, nodes are normally ordered alphabetically. This can
            be overridden by setting this to a value other than 0.

        :match_candidates:
            Modifies the behaviour of the parser when matching completion
            candidates.

            The :meth:`candidates` method returns a list of words that match at the
            current token, which are then used for completion.  If
            ``match_candidates=True`` the allowed input will be explicitly
            constrainted to just these candidates.

            ``match_candidates`` will be set automatically if
            :meth:`candidates` is provided.

            Useful for situations where you have a general regex pattern (eg. a
            pattern matching files) but a known set of matches at this point
            (eg.  files in the current directory).

        :cull_candidates:
            If ``True`` (the default) :meth:`candidates` may return a static
            list of candidates that is automatically culled based on the text
            being matched. This avoids a lot of boiler plate code.

            >>> a = Node(candidates=['one', 'two'])
            >>> print list(a.candidates(None, ''))
            ['one ', 'two ']
            >>> print list(a.candidates(None, 'o'))
            ['one ']

        :traversals:
            The number of times this node can match in any parse context.
            :class:`Alias` nodes allow for multiple traversal.

            If ``traversals=0`` the node will match an infinite number of times.

        :label:
            Specify the global label for this node. This can be used by the
            :class:`Alias` to refer to nodes by label rather than path.
    """
    pattern = None
    separator = r'\s+|\s*$'
    order = 0
    match_candidates = False
    cull_candidates = True
    traversals = 1
    label = None

    def __init__(self, *anonymous, **kwargs):
        self._children = {}
        self._group = None
        help = kwargs.pop('help', '')
        if isinstance(help, basestring):
            self._help = help
        elif callable(help):
            self.help = help
        else:
            raise InvalidHelp('help must be a callable or a string')
        if 'pattern' in kwargs:
            self.pattern = kwargs.pop('pattern')
        if 'separator' in kwargs:
            self.separator = kwargs.pop('separator')
        if 'candidates' in kwargs:
            candidates = kwargs.pop('candidates')
            if callable(candidates):
                self.candidates = candidates
            else:
                self.candidates = lambda c, t: candidates
            self.match_candidates = True
        self.cull_candidates = kwargs.pop('cull_candidates', self.cull_candidates)
        if self.cull_candidates:
            def cull(context, text):
                return cull_candidates(cull.candidates(context, text), text)
            cull.candidates = self.candidates
            self.candidates = cull
        if self.pattern is not None:
            self._pattern = re.compile(self.pattern)
        self._separator = re.compile(self.separator)
        if self.pattern is not None and self.separator is not None:
            self._full_match = re.compile('(?:%s)(?:%s)' %
                                          (self.pattern, self.separator))
        self.name = kwargs.pop('name', None)
        self.parent = None
        self.__anonymous_children = 0
        self(*anonymous, **kwargs)

    def _get_group(self):
        if self._group is None and self.parent:
            return self.parent.group
        return self._group or 0

    def _set_group(self, group):
        self._group = group

    group = property(lambda self: self._get_group(),
                     lambda self, value: self._set_group(value))

    def _set_name(self, name):
        """Set the name of this node.

        If the Node does not have an existing matching pattern associated with
        it, a pattern will be created using the name.
        """
        self._name = name
        if isinstance(name, basestring) and self.pattern is None:
            self.pattern = name
            self._pattern = re.compile(name)
        if self.pattern is not None and self.separator is not None:
            self._full_match = re.compile('(?:%s)(?:%s)' %
                                          (self.pattern, self.separator))
    name = property(lambda self: self._name,
                    lambda self, name: self._set_name(name))

    def help(self, context):
        """Return help for node.

        :returns: A sequence of tuples in the form (lhs, help).
        """
        if self.name == self.pattern:
            yield (self.name, self._help)
        else:
            yield ('<%s>' % self.name, self._help)

    def __call__(self, *anonymous, **options):
        """Update or add options and child nodes.

        Positional arguments are treated as anonymous child nodes, while
        keyword arguments can either be named child nodes or attribute updates
        for this node. See __init__ for more information on attributes.

        >>> top = Node(name='top')
        >>> top(subnode=Node())
        <Node:/top>
        >>> top.find('/subnode')
        <Node:/top/subnode>
        """
        for node in anonymous:
            if not isinstance(node, Node):
                raise InvalidAnonymousNode('"%r" must be a Node object' % node)
            # TODO Convert help to name instead of __anonymous_<n>
            node.name = '__anonymous_%i' % self.__anonymous_children
            node.parent = self
            self._children[node.name] = node
            self.__anonymous_children += 1

        for k, v in options.iteritems():
            if isinstance(v, Node):
                k = k.rstrip('_')
                v.name = k
                v.parent = self
                self._children[k] = v
            else:
                try:
                    setattr(self, k, v)
                except AttributeError:
                    raise AttributeError('Can\'t set attribute "%s"' % k)
        return self

    def __iter__(self):
        """Iterate over child nodes, ignoring context.

        >>> tree = Node()(two=Node(), three=Node())
        >>> list(tree)
        [<Node:/three>, <Node:/two>]
        """
        def nat_tokenise(key, splitter=re.compile(r'(\d+)')):
            def convert(k):
              if k.isdigit():
                return int(k)
              return k
            return [convert(el) for el in splitter.split(key)]

        children = sorted(self._children.values(),
                          key=lambda i: (i.group, i.order, nat_tokenise(i.name)))
        for child in children:
            yield child

    def __setitem__(self, key, child):
        """Emulate dictionary set.

        >>> node = Node()
        >>> node['two'] = Node()
        >>> list(node.walk())
        [<Node:/>, <Node:/two>]
        """
        self(**{key: child})

    def __getitem__(self, key):
        """Emulate dictionary get.

        >>> node = Node()(two=Node())
        >>> node['two']
        <Node:/two>
        """
        return self._children[key]

    def __delitem__(self, key):
        """Emulate dictionary delete.

        >>> node = Node(two=Node(), three=Node())
        >>> list(node.walk())
        [<Node:/>, <Node:/three>, <Node:/two>]
        >>> del node['two']
        >>> list(node.walk())
        [<Node:/>, <Node:/three>]
        """
        child = self._children.pop(key)
        child.parent = None

    def __contains__(self, key):
        """Emulate dictionary key existence test.

        >>> node = Node(two=Node(), three=Node())
        >>> 'two' in node
        True
        """
        return key in self._children

    def walk(self, predicate=None):
        """Perform a recursive walk of the grammar tree.

        >>> tree = Node(two=Node(three=Node(), four=Node()))
        >>> list(tree.walk())
        [<Node:/>, <Node:/two>, <Node:/two/four>, <Node:/two/three>]
        """
        if predicate is None:
            predicate = lambda node: True

        def _walk(root):
            if not predicate(root):
                return
            yield root
            for node in root._children.itervalues():
                for subnode in _walk(node):
                    yield subnode

        for node in _walk(self):
            yield node

    def children(self, context, follow=False):
        """Iterate over child nodes, optionally follow()ing branches.

        >>> from cly import *
        >>> grammar = Grammar(two=Node(three=Node(),
        ...                            four=Node()),
        ...                            five=Alias(target='../two/*'))
        >>> parser = Parser(grammar)
        >>> context = Context(parser, None)
        >>> list(grammar.children(context))
        [<Alias:/five for /two/*>, <Node:/two>]
        >>> list(grammar.children(context, follow=True))
        [<Node:/two/four>, <Node:/two/three>, <Node:/two>]
        """
        for child in self:
            if child.valid(context):
                if follow:
                    for branch in child.follow(context):
                        if branch.valid(context):
                            yield branch
                else:
                    yield child

    def follow(self, context):
        """Return alternative Nodes to traverse.

        The children() method calls this method when follow=True to expand
        aliased nodes, although it could be used for other purposes."""
        yield self

    def selected(self, context, match):
        """This node was selected by the parser.

        By default, informs the context that the node has been traversed."""
        context.selected(self)

    def next(self, context):
        """Return an iterable over the set of next candidate nodes."""
        for child in self.children(context, follow=True):
            yield child

    def match(self, context):
        """Does this node match the current token?

        Must return a regex match object or None for no match. If
        ``match_candidates`` is true the token must also match one of the values
        returned by ``candidates()``.

        Must include separator in determining whether a match was
        successful."""
        if not self.valid(context):
            return None
        match = self._pattern.match(context.command, context.cursor)
        if match:
            # Check that separator matches as well
            if not self._separator.match(context.command, context.cursor +
                                         len(match.group())):
                return None
            if self.match_candidates and match.group() + ' ' not in \
                    self.candidates(context, match.group()):
                return None
            return match

    def advance(self, context):
        """Advance context cursor based on this nodes match."""
        match = self._full_match.match(context.command, context.cursor)
        context.advance(len(match.group()))

    def visible(self, context):
        """Should this node be visible?"""
        return True

    def terminal(self, context):
        """This node was selected as a terminal."""
        raise UnexpectedEOL(context)

    def depth(self):
        """The depth of this node in the grammar.

        >>> grammar = Grammar(one=Node(), two=Node())
        >>> grammar.depth()
        0
        >>> grammar.find('/two').depth()
        1
        """
        return self.parent and self.parent.depth() + 1 or 0

    def path(self):
        """The full grammar path to this node. Path components are separated
        by a forward slash.

        >>> grammar = Grammar(one=Node(), two=Node())
        >>> grammar.find('/two').path()
        '/two'
        """
        names = []
        node = self
        while node is not None:
            if node.name is not None:
                names.insert(0, node.name)
            node = node.parent
        return '/' + '/'.join(names)

    def candidates(self, context, text):
        """Return an iterable of completion candidates for the given text. The
        default is to use the content of :meth:`help`.

        if the ``Node.cull_candidates`` attribute is True then results from
        :meth:`candidates` will automatically be filtered for text matching the
        prefix ``text``.

        :param text: Text entered so far.

        >>> class Custom(Node):
        ...   def help(self, context):
        ...     return 'Some help'
        >>> grammar = Grammar(one=Node(), two=Custom())
        >>> list(grammar.find('/one').candidates(None, 'o'))
        ['one ']
        >>> list(grammar.find('/two').candidates(None, 't'))
        ['two ']

        If the text prefix does not match any of the candidates returned, an
        empty list is returned:

        >>> list(grammar.find('/one').candidates(None, 'f'))
        []
        """
        help = self.help(context)
        if isinstance(help, basestring):
            if self.name == self.pattern:
                yield self.name
        else:
            for key, _ in help:
                if key[0] != '<':
                  yield key

    def find(self, path):
        """Find a Node by path rooted at this node.

        :param path: "Path" to the node, or a label.
        :returns: Found node.

        >>> top = Node(name='top', one=Node(),
        ...            two=Node(three=Node()))
        >>> top.find('/two/three')
        <Node:/top/two/three>
        >>> top.find('/one/bar')
        Traceback (most recent call last):
        ...
        InvalidNodePath: /top/one/bar
        """
        if self.label == path:
            return self
        components = filter(None, path.split('/'))
        if not components:
            return self
        for child in self:
            if not path.startswith('/'):
                return child.find(path)
            elif child.name == components[0]:
                return child.find('/' + '/'.join(components[1:]))
        if path.startswith('/'):
            raise InvalidNodePath(posixpath.join(self.path(), path.strip('/')))
        else:
            raise InvalidNodePath(path)

    def valid(self, context):
        """Is this node valid in the given context?"""
        # Node is invalid if traversed more than self.traversals times
        return not self.traversals or \
            context.traversed(self) < self.traversals

    def _get_anonymous(self):
        """Is this node anonymous?"""
        return self.name.startswith('__anonymous_')

    anonymous = property(_get_anonymous, doc=_get_anonymous.__doc__)

    def update(self, node):
        """Merge another node into this one.

        If a merging node collides with an existing one, the existing node
        will be preserved and the merging nodes children merged.

        :param node: Node to merge into this.
        """
        self.__anonymous_children += node.__anonymous_children
        for key, child in node._children.iteritems():
            if key not in self:
                self[key] = child
            else:
                self[key].update(child)

    def __repr__(self):
        return '<%s:%s>' % (self.__class__.__name__, self.path() or '<root>')

    @classmethod
    def cast_attribute(cls, namespace, name, value):
        """Define functions for casting attributes to their correct Python type.

        Upcalling is necessary.

        :param namespace: The XML namespace of the attribute. Compare against
                    XMLGrammar.EVAL_NS to determine if forced evaluation
                    can/should occur.
        :param name: Attribute name.
        :param value: Value to cast.

        :returns: Tuple of (value, options) where options is a dictionary of
                  extra Node constructor arguments.
        """
        casts = {
            'traversals': int, 'group': group_cast,
            'order': int, 'match_candidates': boolean_cast,
            'with_context': boolean_cast,
            }
        if name in casts:
            return casts[name](value), {}

        # Attributes that can be strings but by default have a method.
        if name == 'help' and namespace != XMLGrammar.EVAL_NS:
            return value, {}

        # Is the destination Node attribute callable? Do a lazy eval.
        function = getattr(cls, name, None)
        if callable(function):
            args, _, _, _ = getargspec(function)
            if args and args[0] == 'self':
                args.pop(0)
            value = lazy_attr_evaluator(value, args)
        return value, {}

    @classmethod
    def attribute_aliases(cls):
        """Define attribute aliases for this node.

        Parent classes are automatically merged, so upcalling is unnecessary.

        :returns: Mapping of old to new keys.
        """
        return {'if': 'valid'}


class Masquerade(Node):
    """A node that masquerades as other nodes.

    Masquerade is a general-purpose tool for dynamically inserting nodes into
    the grammar at the current location. Implementations should override the
    ``masqueraded()`` method.

    Use cases:

      - Conditionally present nodes.
      - Dynamically generated nodes.
      - Aliases for other parts of the grammar.

    >>> from cly.parser import Parser
    >>> class Privileged(Masquerade):
    ...     authenticated = False
    ...     def masqueraded(self, context):
    ...         if not self.authenticated:
    ...             return []
    ...         shutdown = Node(Action(self.shutdown), name='shutdown')
    ...         return [shutdown]
    ...     def shutdown(self):
    ...         print 'shutdown()'
    >>> privileged = Privileged()
    >>> parser = Parser(Grammar(privileged, one=Node()))
    >>> parser.execute('shutdown')
    Traceback (most recent call last):
    ...
    InvalidToken: invalid token 'shutdown'
    >>> privileged.authenticated = True
    >>> parser.execute('shutdown')
    shutdown()
    """

    def masqueraded(self, context):
        """Return a sequence of all masqueraded nodes.

        Masquerades as child nodes by default.
        """
        return super(Masquerade, self).children(context, follow=True)

    def selected(self, context, match):
        raise SystemError('Masqueraded nodes should never be selected')

    def follow(self, context):
        return list(self.masqueraded(context))

    def visible(self, context):
        for node in self.masqueraded(context):
            if node.visible(context):
                return True
        return False

    def valid(self, context):
        for node in self.masqueraded(context):
            if node.valid(context):
                return True
        return False


class Defaults(Masquerade):
    """Set variables in a branch.

    This is primarily useful in XML grammars.

    >>> from cly import *
    >>> parser = Parser(Grammar(Defaults(foo=10, bar=20)(baz=Node())))
    >>> parser.parse('baz').vars
    {'foo': 10, 'bar': 20}

    In an XML grammar, all attributes are evaluated. This means that strings
    must be double quoted.
    """
    vars = ''
    unset = ''

    def __init__(self, **kwargs):
        super(Defaults, self).__init__()
        self.vars = kwargs

    def follow(self, context):
        context.vars.update(self.vars)
        return super(Defaults, self).follow(context)

    @classmethod
    def cast_attribute(cls, namespace, name, value):
        return eval(value), {}


class Group(Masquerade):
    """Group subnodes under a single group ID.

    :param id: Group ID.
    """
    def __init__(self, id=None, *args, **kwargs):
        super(Group, self).__init__(group=id, *args, **kwargs)

    @classmethod
    def cast_attribute(cls, namespace, name, value):
        if name == 'id':
            return group_cast(value), {}
        return super(Group, cls).cast_attribute(namespace, name, value)


class Alias(Masquerade):
    """An alias for another node, or set of nodes.

    An Alias overrides the ``follow()`` method to return aliased Nodes. Globs
    are supported.

    :param target:
        Relative or absolute path to the aliased node. If the alias contains
        glob characters (``*`` or ``?``) all matching nodes are aliased.

    >>> from cly.parser import Parser, Context
    >>> parser = Parser(Grammar(one=Node(), two=Node(
    ...                 three=Node()), four=Alias(target='../one'),
    ...                 five=Node(six=Alias(target='../../*'))))
    >>> alias = parser.find('/four')
    >>> alias
    <Alias:/four for /one>
    >>> context = Context(parser, None)
    >>> list(alias.follow(context))
    [<Node:/one>]
    >>> alias = parser.find('/five/six')
    >>> alias
    <Alias:/five/six for /*>
    >>> list(alias.follow(context))
    [<Node:/five>, <Node:/one>, <Node:/one>, <Node:/two>]
    """

    pattern = ''
    _target = None

    def __init__(self, target, *anonymous, **kwargs):
        self._target = target
        Node.__init__(self, help='<alias for "%s">' % self._target,
                      *anonymous, **kwargs)

    def masqueraded(self, context):
        """Return an iterable of all aliased nodes."""
        # Find label path, if any
        if '/' in self._target:
            label, path = self._target.split('/', 1)
        else:
            label, path = self._target, ''
        if label in context.parser.labels:
            node = context.parser.labels[label]
            target = posixpath.normpath(posixpath.join(node.path(), path))
        else:
            target = self.target

        root = self
        while root.parent:
            root = root.parent
        try:
            yield root.find(target)
        except InvalidNodePath:
            from fnmatch import fnmatch
            start = root.find(posixpath.dirname(target))
            match = posixpath.basename(target)
            for child in start.children(context, follow=True):
                if fnmatch(child.name, match):
                    yield child

    def _get_target(self):
        """Absolute (normalised) path to the aliased node."""
        return posixpath.normpath(posixpath.join(self.path(), self._target))

    target = property(_get_target)

    def __repr__(self):
        return '<%s:%s for %s>' % (self.__class__.__name__, self.path(),
                                   self.target)


class If(Masquerade):
    """A set of conditional nodes.

    A node that masquerades as its children, if a condition is true.

    :param test: A callable with the signature ``test(context)``.
                 Returns ``True`` if masqueraded nodes are accessible.

    All other arguments are passed through to the default :class:`Node` constructor.

    >>> from cly.parser import Parser
    >>> active = False
    >>> parser = Parser(Grammar(If(lambda c: active, one=Node())))
    >>> parser.parse('one')
    <Context command:'one' remaining:'one'>
    >>> active = True
    >>> parser.parse('one')
    <Context command:'one' remaining:''>
    """

    def __init__(self, test, *args, **kwargs):
        kwargs['test'] = test
        super(If, self).__init__(*args, **kwargs)

    def masqueraded(self, context):
        if not self.test(context):
            return []
        return super(If, self).masqueraded(context)

    def test(self, context):
        raise NotImplementedError


class Apply(Masquerade):
    """Apply settings to all ancestor nodes.

    Terminates application of settings on any deeper Apply node.

    Before applying settings:

    >>> top = Node(one=Node(), two=Node(three=Node()))
    >>> [node.traversals for node in top.walk()]
    [1, 1, 1, 1]

    And after applying settings:

    >>> apply = Apply(traversals=0)(top)
    >>> [node.traversals for node in top.walk()]
    [0, 0, 0, 0]
    """
    def __init__(self, **apply):
        self._apply = apply
        super(Apply, self).__init__()

    def __call__(self, *anonymous, **kwargs):
        result = Node.__call__(self, *anonymous, **kwargs)

        def stop_on_ancestors(node):
            return node is self or not isinstance(node, Apply)

        for child in self.walk(predicate=stop_on_ancestors):
            if child is self:
                Node.__call__(self, **self._apply)
            else:
                child(**self._apply)

        return result



class Action(Node):
    """Matches EOL and executes ``callback``.

    :param callback: Callback to execute when the action is chosen.

    :var with_context:
        If True, passes the current parse :class:`~cly.parser.Context` as the
        first argument.

    >>> from cly.parser import Parser, Context
    >>> def write_text():
    ...     print 'some text'
    >>> grammar = Grammar(action=Action(callback=write_text))
    >>> parser = Parser(grammar)
    >>> context = Context(parser, 'foo bar')
    >>> node = grammar.find('/action')
    >>> node.help(None)
    (('<eol>', ''),)
    >>> node.terminal(context)
    some text
    """
    pattern = '$'
    with_context = None

    def __init__(self, callback, *anonymous, **kwargs):
        help = kwargs.pop('help', '')
        kwargs.setdefault('group', 9999)
        if isinstance(help, basestring):
            help_string = help
            help = lambda ctx: (('<eol>', help_string),)
        Node.__init__(self, help=help, callback=callback, *anonymous, **kwargs)

    def terminal(self, context):
        if self.with_context:
            return self.callback(context, **context.vars)
        else:
            return self.callback(**context.vars)

    def callback(self, *args, **kwargs):
        raise UnexpectedEOL(None)

    def selected(self, context, match):
        # We don't "traverse" Action nodes, because they are always terminal,
        # and if we do they get excluded from help.
        pass

    @classmethod
    def attribute_aliases(cls):
        aliases = {'exec': 'callback'}
        aliases.update(super(Action, cls).attribute_aliases())
        return aliases

    @classmethod
    def cast_attribute(cls, namespace, name, value):
        options = {}
        if name == 'callback':
            args = ['context']
            options['with_context'] = True
            value = lazy_attr_evaluator(value, args)
            return value, options
        return super(Action, cls).cast_attribute(namespace, name, value)


class Variable(Node):
    """Parse and record the users input in the vars member of the context.

    The node name is used as the variable name unless var_name is provided to
    the constructor.

    If ``traversals != 1`` the variable will accumulate values into a list.
    """

    pattern = r'\w+'

    def __init__(self, *anonymous, **kwargs):
        self.var_name = kwargs.pop('var_name', None)
        Node.__init__(self, *anonymous, **kwargs)

    def _set_var_name(self, value):
        if value is not None:
            value = str(value)
        self._var_name = value

    def _get_var_name(self):
        """Get the var name for this variable. Will use ``var_name`` if
        provided to the constructor, otherwise it will use the node name."""
        if self._var_name is not None:
            return self._var_name
        return self.name

    var_name = property(_get_var_name, _set_var_name)

    def valid(self, context):
        valid = Node.valid(self, context)
        if self.traversals == 1:
            return valid
        if self.traversals != 1:
            return valid
        if len(context.vars.get(self.name, [])) < self.traversals:
            return valid
        return False

    def selected(self, context, match):
        """Convert the match to a value with self.parse(), then add
        the result to the context "vars" member.

        Raises ValidationError if the variable raises InvalidMatch.

        >>> from cly.parser import Context
        >>> c = Context(None, 'foo bar')
        >>> v = Variable(name='var')
        >>> v.selected(c, re.match(r'\w+', 'test'))
        >>> c.vars['var']
        'test'
        """
        try:
            value = self.parse(context, match)
        except ValidationError, e:
            raise ValidationError(context, token=match.group(),
                                  exception=unicode(e))
        if not self.traversals or self.traversals > 1:
            context.vars.setdefault(self.var_name, []).append(value)
        else:
            context.vars[self.var_name] = value
        return Node.selected(self, context, match)

    def parse(self, context, match):
        """Parse the match and return a value. Value can be of any type: tuple,
        list, object, etc.

        Must throw a ValidationError if the input is invalid. Alternate
        variables should override this method.

        >>> v = Variable()
        >>> v.parse(None, re.match(r'\w+', 'test'))
        'test'
        """
        return match.group()


class Grammar(Node):
    """The root node for a grammar."""
    pattern = '^'

    def __init__(self, *anonymous, **kwargs):
        Node.__init__(self, help='<root>', *anonymous, **kwargs)

    def terminal(self, context):
        """Null-op for empty lines."""


class XMLGrammar(Grammar):
    """A Grammar that builds its structure from an XML file.

    The XML grammar is a simple mapping from element names to :class:`Node`
    subclasses, and element attributes to constructor arguments. Unlike when
    building a grammar from :class:`Node` objects, the ``name`` must be
    explicitly provided.

    Arguments:
        :file: Filename or file-like object to load XML grammar from.
        :extra_nodes: A sequence of extra :class:`Node` subclasses to make
                      available as elements.

    eg.

    .. code-block:: xml

        <word name="abc" valid="'var' in v" pattern=r"[abc]+"/>

    Is roughly equivalent to:

    .. code-block:: python

        ...(
          abc=Word(valid=lambda context: 'var' in context.vars,
                   pattern=r'[abc]+')
        )

    Attributes that are methods on the :class:`Node` will be evaluated as expressions.
    All variables from the parse :class:`~cly.parser.Context`, "data"
    dictionary, and keyword arguments (in that order) are available as locals
    to the evaluated expression, as well as some additional variables:

        :c: :class:`~cly.parser.Context` object.
        :v: All variables from the :class:`~cly.parser.Context`.
        :d: The "data" dictionary.
        :a: Any positional arguments.
        :kw: Any keyword arguments.

    v in particular is useful for passing all collected arguments to
    functions.

    Some convenient aliases also exist to make life easier when using XML
    grammars.

    Node aliases:

        :var: variable
        :int: integer
        :str: string

    Attribute aliases:

        :if: valid
        :exec: callback

    eg.

    .. code-block:: xml

      <?xml version="1.0"?>
      <grammar xmlns="http://swapoff.org/cly/xml">
        <node name="echo" help="Echo text">
          <action if="defined('text')" exec="echo(**v)"/>
          <group traversals="0">
            <variable name="text" help="Text to echo">
              <alias target="/echo/*"/>
            </variable>
          </group>
        </node>
        <action name="quit" callback="sys.exit(0)" help="Quit"/>
      </grammar>

    And used with:

    .. code-block:: python

      def echo(text):
        print text

      g = XMLGrammar('example.xml')
      interact(g, data={'echo': echo})

    """

    NODE_ALIASES = {
        'var': 'variable',
        'int': 'integer',
        'str': 'string',
        }
    EVAL_NS = 'http://swapoff.org/cly/xml/eval'

    def __init__(self, file, extra_nodes=None):
        super(XMLGrammar, self).__init__()

        dom = minidom.parse(file)

        nodes = [n for n in [globals()[k] for k in __all__]
                 if isclass(n) and issubclass(n, Node)]
        nodes.extend(extra_nodes or [])
        self.node_map = dict([(v.__name__.lower(), v) for v in nodes])
        self.node_map.update([(k, self.node_map[v])
                              for k, v in self.NODE_ALIASES.items()])

        grammar = dom.firstChild
        if grammar.localName != 'grammar':
            raise XMLParseError('Invalid root element "%s", expected "grammar"'
                                % grammar.localName)

        attributes = self.parse_attributes(self.__class__, grammar)
        self(**attributes)
        self.parse_xml(self, grammar.firstChild)

    def parse_xml(self, parent, xnode):
        if not xnode:
            return

        if xnode.nodeType == minidom.Node.ELEMENT_NODE:
            node = self.parse_element(parent, xnode)
        else:
            node = parent

        self.parse_xml(node, xnode.firstChild)
        self.parse_xml(parent, xnode.nextSibling)

    def parse_element(self, parent, xnode):
        node_name = xnode.localName.lower()
        cls = self.node_map.get(node_name)
        if not cls:
            raise XMLParseError('Invalid node type "%s"' % node_name)

        attributes = self.parse_attributes(cls, xnode)

        # Construct Node
        name = attributes.pop('name', None)
        try:
            node = cls(**attributes)
        except Exception, e:
            e.args = ('Node construction of %s failed: %s' % (cls, e),)
            raise

        # Tell parent node about new child.
        if name:
            parent(**{str(name): node})
        else:
            parent(node)

        return node

    def parse_attributes(self, cls, xnode):
        # Delegate to node classes for attribute aliases and type conversion
        # callbacks.
        aliases = {}
        for c in reversed(cls.mro()):
            if 'attribute_aliases' in c.__dict__:
                aliases.update(c.attribute_aliases())

        attributes = {}

        for (ns, k), v in xnode.attributes.itemsNS():
            # Do type conversion
            k = str(aliases.get(k, k))
            v, options = cls.cast_attribute(ns, k, v)
            attributes.update(options)
            attributes[k] = v
        return attributes


def lazy_attr_evaluator(attr, positional_args=None):
    """Return a callable that lazily evaluates an expression.

    Arguments:
        :attr: Python expression to evaluate as a string.
        :positional_args: List of positional argument names to map to locals.
    """
    # Extract positional arguments from function object
    positional_args = positional_args or []
    def attr_evaluator(*args, **kwargs):
        locals = dict(kwargs)

        # Convert positional args into locals
        if args:
            if not positional_args or len(positional_args) < len(args):
                raise XMLParseError(
                    'Lazily evaluated XML attribute "%s" called with unknown '
                    'positional arguments. This is not supported.' % attr
                    )
            locals.update(zip(positional_args[:len(args)], args))

        if 'context' in locals:
            context = locals.pop('context')
            data = context.data
            if isinstance(data, dict):
                locals.update(data)
            vars = context.vars
        else:
            context = None
            data = {}
            vars = {}

        def defined(vars, any=False):
            """Test if all (or any) of vars are defined."""
            for var in vars.split():
                defined = var in locals
                if any and defined:
                    return True
                elif not any and not defined:
                    return False
            return not any

        locals.update(vars)
        locals['defined'] = defined
        locals['v'] = vars
        locals['a'] = args
        locals['kw'] = kwargs
        locals['d'] = data
        locals['c'] = context
        if context is not None:
            context.update_locals(locals)
        return eval(attr, locals)
    return attr_evaluator


def boolean_cast(value):
    """Converter for boolean attributes."""
    return str(value).lower() in ('true', '1', 'yes')


def group_cast(value):
    """Parse a group="n" attribute."""
    try:
        return int(value)
    except ValueError:
        return value


class Help(object):
    """A callable object representing help for a Node.

    Returns an iterable of pairs in the form (key, help).

    Arguments:

        :doc:
            An iterable of two element tuples in the form ``(key, help)``.

    >>> h = Help([('a', 'b'), ('b', 'c')])
    >>> [i for i in h(None)]
    [('a', 'b'), ('b', 'c')]
    """
    def __init__(self, doc):
        self.doc = doc

    def __call__(self, context):
        """Returns an iterable of two element tuples in the form (key, help)."""
        for n, h in self.doc:
            yield (n, h)

    @staticmethod
    def pair(name, help):
        """Create a Help object from a single ``(name, help)`` pair.

        >>> h = Help.pair('a', 'b')
        >>> [i for i in h(None)]
        [('a', 'b')]
        """
        return Help([(name, help)])


class LazyHelp(Help):
    """Extract help key from a node.

    Used internally by Node when a string is provided as help.

    If the Node does not have a custom pattern, the help will be in the form
    (name, text), otherwise it will be in the form (<name>, text).
    """
    def __init__(self, node, text):
        self.node = node
        self.text = text

    def __call__(self, context):
        """Extract help key from node.

        >>> node = Node(name='test')
        >>> help = LazyHelp(node, 'Moo')
        >>> [i for i in help(None)]
        [('test', 'Moo')]
        """
        if self.node.name == self.node.pattern:
            yield (self.node.name, self.text)
        else:
            yield ('<%s>' % self.node.name, self.text)


class Word(Variable):
    """Matches a Pythonesque variable name.

    >>> from cly.parser import Parser
    >>> parser = Parser(Grammar(foo=Word()))
    >>> parser.parse('a123').vars['foo']
    'a123'
    >>> parser.parse('123').remaining
    '123'
    """
    pattern = r'(?i)[A-Z_]\w*'


class Keyword(Variable):
    """Matches and stores the node name only.

    >>> from cly.parser import Parser
    >>> parser = Parser(Grammar(foo=Keyword()))
    >>> parser.parse('foo').vars['foo']
    'foo'
    >>> parser.parse('bar').vars['foo']
    Traceback (most recent call last):
    ...
    KeyError: 'foo'
    """
    pattern = None


class KeyValue(Variable):
    """Match and store a key value pair."""

    def __init__(self, sep='=', value_pattern=r'\S+', *args, **kwargs):
        pattern = kwargs.pop('pattern', r'(\w+)\s*' + sep + '\s*(' + value_pattern + ')')
        super(KeyValue, self).__init__(pattern=pattern, *args, **kwargs)

    def parse(self, context, match):
        return match.group(1), match.group(2)


class String(Variable):
    """Matches either a bare word or a quoted string.

    >>> from cly.parser import Parser
    >>> parser = Parser(Grammar(foo=String()))
    >>> parser.parse('"foo bar"').vars['foo']
    'foo bar'
    >>> parser.parse('foo_bar').vars['foo']
    'foo_bar'
    """
    pattern = r"""(\w+)|"([^"\\]*(?:\\.[^"\\]*)*)"|'([^'\\]*(?:\\.[^'\\]*)*)'"""

    def parse(self, context, match):
        return match.group(match.lastindex).decode('string_escape')


class Base64(Variable):
    """Matches a base64 encoded string.

    >>> from cly.parser import Parser
    >>> parser = Parser(Grammar(foo=Base64()))
    >>> parser.parse('Y2x5').vars['foo']
    'cly'
    >>> parser.parse('aXM=').vars['foo']
    'is'
    >>> parser.parse('Y29vbA==').vars['foo']
    'cool'
    >>> # Fails because there is not enough chars
    >>> parser.parse('Y2x').vars.get('foo')
    >>> # Fails because there are too many '=' pad characters
    >>> parser.parse('Y2x5=').vars.get('foo')
    >>> # Fails because there are too many '=' pad characters
    >>> parser.parse('Y2x5==').vars.get('foo')
    >>> # Fails because there are too many '=' pad characters
    >>> parser.parse('Y2x5===').vars.get('foo')
    >>> # Fails because there are trailing characters
    >>> parser.parse('Y29vbA==abc').vars.get('foo')
    """
    pattern = r"""(?:([A-Za-z0-9+/]{2}==)|([A-Za-z0-9+/]{3}=)){1}|([A-Za-z0-9+/]{4})+(?:([A-Za-z0-9+/]{2}==)|([A-Za-z0-9+/]{3}=))?"""

    def parse(self, context, match):
        return match.group().decode('base64_codec')


class URI(Variable):
    """Matches a URI. Result is a string.

    >>> from cly.parser import Parser
    >>> parser = Parser(Grammar(foo=URI()))
    >>> parser.parse('http://www.example.com/test/;test?a=10&b=10#fragment').vars['foo']
    'http://www.example.com/test/;test?a=10&b=10#fragment'
    """
    pattern = r"""(([a-zA-Z][0-9a-zA-Z+\\-\\.]*:)?/{0,2}[0-9a-zA-Z;/?:@&=+$\\.\\-_!~*'()%]+)(#[0-9a-zA-Z;/?:@&=+$\\.\\-_!~*'()%]+)?"""

    def __init__(self, scheme='', allow_fragments=1, *anonymous, **kwargs):
        Variable.__init__(self, *anonymous, **kwargs)
        self.scheme = scheme
        self.allow_fragments = allow_fragments

    #def parse(self, context, match):
        #import urlparse
        #return urlparse.urlparse(match.string[match.start():match.end()], self.scheme, self.allow_fragments)


class LDAPDN(Variable):
    """Matches an LDAP DN.

    >>> from cly.parser import Parser
    >>> parser = Parser(Grammar(foo=LDAPDN()))
    >>> parser.parse('cn=Manager,dc=example,dc=com').vars['foo']
    'cn=Manager,dc=example,dc=com'
    """
    pattern = r'(\w+=\w+)(?:,(\w+=\w+))*'


class Integer(Variable):
    """Matches an integer.

    >>> from cly.parser import Parser
    >>> parser = Parser(Grammar(foo=Integer()))
    >>> parser.parse('12345').vars['foo']
    12345
    >>> parser.parse('123.45').remaining
    '123.45'
    """
    pattern = r'[-+]?\d+'

    def parse(self, context, match):
        return int(match.group())


class Boolean(Variable):
    """Matches a boolean.

    >>> from cly.parser import Parser
    >>> parser = Parser(Grammar(foo=Boolean()))
    >>> parser.parse('true').vars['foo']
    True
    >>> parser.parse('no').vars['foo']
    False
    """
    TRUE = 'true yes aye enable enabled on 1'.split()
    FALSE = 'false no disable disabled off 0'.split()

    pattern = r'(?i)(%s)' % '|'.join(TRUE + FALSE)

    def parse(self, context, match):
        boolean = match.group()
        return boolean in self.TRUE


class Float(Variable):
    """Matches a floating point number.

    >>> from cly.parser import Parser
    >>> parser = Parser(Grammar(foo=Float()))
    >>> parser.parse('12345.34').vars['foo']
    12345.34
    >>> parser.parse('123.45e10').vars['foo']
    1234500000000.0
    """
    pattern = r'[-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?'

    def parse(self, context, match):
        return float(match.group())


class IP(Variable):
    """Match an IP address.

    >>> from cly.parser import Parser
    >>> parser = Parser(Grammar(foo=IP()))
    >>> parser.parse('123.34.67.89').vars['foo']
    '123.34.67.89'

    Invalid IP addresses will not match:

    >>> parser.parse('123.34.67.899').vars['foo']
    Traceback (most recent call last):
    ...
    KeyError: 'foo'

    Also matches netmasks:

    >>> parser.parse('255.255.255.0').vars['foo']
    '255.255.255.0'
    """
    pattern = r'(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)'


class CIDR(Variable):
    """Match a CIDR network representation.

    If a netmask is not provided a default of /32 will be used.

    >>> from cly import *
    >>> parser = Parser(Grammar(foo=CIDR()))
    >>> parser.parse('123.34.67.89').vars['foo']
    '123.34.67.89/32'
    >>> parser.parse('123.34.67.89/24').vars['foo']
    '123.34.67.89/24'
    """
    pattern = r'(%s)(?:/(\d{1,2}))?' % IP.pattern

    def parse(self, context, match):
        mask = match.group(6) or '32'
        return match.group(1) + '/' + mask


class Hostname(Variable):
    """Match only a hostname (not an IP address).

    Arguments:
        :parts: The minimum number of host parts required.
        :suffix: Optional domain suffix to require.

    >>> from cly.parser import *

    Supports bare hostnames:

    >>> parser = Parser(Grammar(foo=Hostname()))
    >>> parser.parse('www').vars
    {'foo': 'www'}

    Fully-qualified names:

    >>> parser.parse('www.example.com').vars
    {'foo': 'www.example.com'}

    IN-ADDR ARPA addresses:

    >>> parser.parse('1.1.10.in-addr.arpa').vars
    {'foo': '1.1.10.in-addr.arpa'}

    But not IP addresses:

    >>> parser.parse('10.1.1.1').vars
    {}

    Suffix checking is also supported:

    >>> parser = Parser(Grammar(foo=Hostname(suffix='.example.com')))
    >>> parser.parse('www').vars
    {}
    >>> parser.parse('www.example.com').vars
    {'foo': 'www.example.com'}

    As well as requiring a minumum number of host parts:

    >>> parser = Parser(Grammar(foo=Hostname(parts=2)))
    >>> parser.parse('www').vars
    {}
    >>> parser.parse('www.foo.com').vars
    {'foo': 'www.foo.com'}
    """
    pattern = r'(?i)([A-Z0-9][A-Z0-9_-]*)((\.([A-Z0-9][A-Z0-9_-]*))*\.([A-Z0-9][A-Z0-9_-]*[A-Z]))?\.?'

    parts = 0
    suffix = None

    def match(self, context):
        match = Variable.match(self, context)
        if match and self.parts and len(match.group().split('.')) < self.parts:
            match = None
        if match and self.suffix and not match.group().endswith(self.suffix):
            match = None
        return match

    @classmethod
    def cast_attribute(cls, namespace, name, value):
        if name == 'parts':
            return int(value)
        return super(Hostname, cls).cast_attribute(namespace, name, value)


class Host(Variable):
    """Match either an IP address or a hostname.

    >>> from cly.parser import Parser
    >>> parser = Parser(Grammar(foo=Host()))
    >>> parser.parse('www.example.com').vars['foo']
    'www.example.com'
    >>> parser.parse('10.1.1.1').vars['foo']
    '10.1.1.1'
    >>> parser.parse('1.1.10.in-addr.arpa').vars['foo']
    '1.1.10.in-addr.arpa'
    """
    pattern = r'(?i)(%s)|(%s)' % (IP.pattern, Hostname.pattern)


class EMail(Variable):
    """Match an E-Mail address.

    >>> from cly.parser import Parser
    >>> parser = Parser(Grammar(foo=EMail()))
    >>> parser.parse('foo@bar.com').vars['foo']
    'foo@bar.com'
    """
    pattern = r'(?i)[A-Z0-9._%-]+@[A-Z0-9.-]+\.[A-Z]{2,4}'


class File(Variable):
    """Match and provide completion candidates for local files.

    >>> from cly.parser import Parser
    >>> parser = Parser(Grammar(foo=File(allow_directories=True)))
    >>> parser.parse('.').vars['foo']
    '.'
    """
    pattern = r'\S+'
    includes = ['*']
    excludes = []
    allow_dotfiles = False
    allow_directories = False

    def match(self, context):
        match = Variable.match(self, context)
        if match and self.match_file(match.group(), self.allow_directories):
            return match

    def match_file(self, file, match_directories=True):
        from fnmatch import fnmatch
        file = os.path.expanduser(file)
        if match_directories and os.path.isdir(file):
            return True
        if not self.allow_dotfiles and os.path.basename(file).startswith('.'):
            return False
        for exclude in self.excludes:
            if fnmatch(file, exclude):
                return False
        for include in self.includes:
            if fnmatch(file, include):
                return True
        return False

    def candidates(self, context, text):
        """Return list of valid file candidates."""

        if text.startswith('~'):
            if '/' in text:
                short_home = text[:text.index('/')]
            else:
                short_home = text
            expanded_home = os.path.expanduser(short_home)
            text = os.path.expanduser(text)
        else:
            short_home = None

        text = os.path.expanduser(text)
        dir = os.path.dirname(text) or os.path.curdir
        file = os.path.basename(text)
        cwd = os.path.curdir + os.path.sep

        def clean(file):
            if file.startswith(cwd):
                return file[len(cwd):]
            if short_home and file.startswith(expanded_home):
                return short_home + file[len(expanded_home):]
            return file

        def get_candidates(dir, file):
            return [f for f in os.listdir(dir) if f.startswith(file)
                    and self.match_file(os.path.join(dir, f))]

        candidates = get_candidates(dir, file)
        if len(candidates) == 1:
            if os.path.isdir(os.path.join(dir, candidates[0])):
                dir = os.path.join(dir, candidates[0] + '/')
                return [dir]
                file = ''
                candidates = get_candidates(dir, file)
            else:
                return [clean(os.path.join(dir, candidates[0] + ' '))]
        return [clean(os.path.join(dir, f))
                for f in candidates if self.allow_dotfiles or f[0] != '.']


class AbsoluteTime(Variable):
    """Parse an absolute time value in the form HH:MM[:SS]].

    :returns: a datetime.time object.
    """
    pattern = r'(\d\d):(\d\d)(?::(\d\d))?'

    def parse(self, context, match):
        hour, minute, second = int(match.group(1)), int(match.group(2)), \
                               int(match.group(3) or 0)
        return datetime.time(hour=hour, minute=minute, second=second)


class RelativeTime(Variable):
    """Parse a relative time.

    Relative times are specified as an optionally negative float followed by a
    single character time unit:

        [-]NN.N[w|d|h|m|s]

    eg.

    15m, 3.5d

    :returns: a datetime.timedelta object.
    """

    units = ['weeks', 'days', 'hours', 'minutes', 'seconds']
    units = dict((u[0], u) for u in units)
    pattern = r'(?i)(%s)([%s])' % (Float.pattern, ''.join(units))

    def parse(self, context, match):
        units = match.group(2).lower()
        value = float(match.group(1))
        args = {self.units[units]: value}
        return datetime.timedelta(**args)


class FixedOffsetTZ(datetime.tzinfo):
    """Fixed offset in minutes east from UTC."""

    def __init__(self, offset, name):
        self._offset = datetime.timedelta(minutes=offset)
        self.zone = name

    def __str__(self):
        return self.zone

    def __repr__(self):
        return '<FixedOffsetTZ "%s" %s>' % (self.zone, self._offset)

    def utcoffset(self, dt):
        return self._offset

    def tzname(self, dt):
        return self.zone

    def dst(self, dt):
        return _zero


class Timezone(Variable):
    """Parse a timezone, using pytz if available."""

    STATIC_TIMEZONES = [
        FixedOffsetTZ(0, 'UTC'),
        FixedOffsetTZ(-720, 'GMT-12:00'), FixedOffsetTZ(-660, 'GMT-11:00'),
        FixedOffsetTZ(-600, 'GMT-10:00'), FixedOffsetTZ(-540, 'GMT-9:00'),
        FixedOffsetTZ(-480, 'GMT-8:00'),  FixedOffsetTZ(-420, 'GMT-7:00'),
        FixedOffsetTZ(-360, 'GMT-6:00'),  FixedOffsetTZ(-300, 'GMT-5:00'),
        FixedOffsetTZ(-240, 'GMT-4:00'),  FixedOffsetTZ(-180, 'GMT-3:00'),
        FixedOffsetTZ(-120, 'GMT-2:00'),  FixedOffsetTZ(-60, 'GMT-1:00'),
        FixedOffsetTZ(0, 'GMT'),           FixedOffsetTZ(60, 'GMT+1:00'),
        FixedOffsetTZ(120, 'GMT+2:00'),   FixedOffsetTZ(180, 'GMT+3:00'),
        FixedOffsetTZ(240, 'GMT+4:00'),   FixedOffsetTZ(300, 'GMT+5:00'),
        FixedOffsetTZ(360, 'GMT+6:00'),   FixedOffsetTZ(420, 'GMT+7:00'),
        FixedOffsetTZ(480, 'GMT+8:00'),   FixedOffsetTZ(540, 'GMT+9:00'),
        FixedOffsetTZ(600, 'GMT+10:00'),  FixedOffsetTZ(660, 'GMT+11:00'),
        FixedOffsetTZ(720, 'GMT+12:00'),  FixedOffsetTZ(780, 'GMT+13:00'),
        ]
    STATIC_TIMEZONES = dict([(z.zone, z) for z in STATIC_TIMEZONES])

    pattern = r'[+:/\w]+'
    match_candidates = True

    if pytz:
        def candidates(self, context, text):
            return cull_candidates(pytz.all_timezones, text)

        def parse(self, context, match):
            return pytz.timezone(match.group())
    else:
        def candidates(self, context, text):
            return cull_candidates(self.STATIC_TIMEZONES, text)

        def parse(self, context, match):
            return self.STATIC_TIMEZONES[match.group()]


def cull_candidates(candidates, text, sep=' '):
    """Cull candidates that do not start with ``text``.

    Returned candidates also have a space appended.

    Arguments:
        :candidates: Sequence of match candidates.
        :text: Text to match.
        :sep: Separator to append to match.

    >>> cull_candidates(['bob', 'fred', 'barry', 'harry'], 'b')
    ['bob ', 'barry ']
    >>> cull_candidates(cull_candidates(['bob', 'fred', 'barry', 'harry'], 'b'), 'b')
    ['bob ', 'barry ']
    """
    return [c.rstrip(sep) + sep for c in candidates if c and c.startswith(text)]
