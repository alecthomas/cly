# -*- coding: utf-8 -*-
#
# Copyright (C) 2006-2007 Alec Thomas <alec@swapoff.org>
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution.
#

import unittest
import doctest
from StringIO import StringIO
from cly.exceptions import InvalidToken
from cly import Defaults, Node, XMLGrammar, Parser


class TestXMLGrammar(unittest.TestCase):
    """Test XML grammar parser."""
    def setUp(self):
        self._output = None

    def _echo(self, *args, **kwargs):
        self._output = (args, kwargs)

    def test_basic(self):
        xml = StringIO("""<?xml version="1.0"?>
        <grammar>
            <node name='echo'>
                <variable name='text'>
                    <action callback='echo(text)'/>
                </variable>
            </node>
        </grammar>
        """)

        grammar = XMLGrammar(xml)
        parser = Parser(grammar, data={'echo': self._echo})
        parser.execute('echo magic')
        self.assertEqual(self._output, (('magic',), {}))

    def test_multiple_traversals(self):
        xml = StringIO("""<?xml version="1.0"?>
        <grammar>
            <node name='echo'>
                <variable name='text' traversals='0'>
                    <alias target='/echo/*'/>
                    <action callback='echo(text)'/>
                </variable>
            </node>
        </grammar>
        """)

        grammar = XMLGrammar(xml)
        parser = Parser(grammar, {'echo': self._echo})
        parser.execute('echo magic monkey')
        self.assertEqual(self._output, ((['magic', 'monkey'],), {}))

    def test_group(self):
        xml = StringIO("""<?xml version="1.0"?>
        <grammar>
            <node name='echo'>
                <variable traversals='0' name='text'>
                    <alias target='../../*'/>
                    <action callback='echo(text)'/>
                </variable>
            </node>
        </grammar>
        """)

        grammar = XMLGrammar(xml)
        parser = Parser(grammar, data={'echo': self._echo})
        parser.execute('echo magic monkey')
        self.assertEqual(self._output, ((['magic', 'monkey'],), {}))

    def test_completion(self):
        xml = StringIO("""<?xml version="1.0"?>
        <grammar>
            <node name="echo">
                <variable name="text" candidates="['monkey', 'muppet']">
                    <action callback="echo(text)"/>
                </variable>
            </node>
        </grammar>
        """)

        def candidates(context, text):
            return ['monkey', 'muppet']

        grammar = XMLGrammar(xml)
        parser = Parser(grammar, data={'echo': self._echo})
        context = parser.parse('echo ')
        self.assertEqual(list(context.candidates()), ['monkey ', 'muppet '])

    def test_node_extension(self):
        from cly.builder import Variable


        class ABC(Variable):
            pattern = r'(?i)[abc]+'


        xml = StringIO("""<?xml version="1.0"?>
        <grammar>
            <node name='echo'>
                <abc name='text'>
                    <action callback='echo(text)'/>
                </abc>
            </node>
        </grammar>
        """)

        grammar = XMLGrammar(xml, extra_nodes=[ABC])
        parser = Parser(grammar, data={'echo': self._echo})
        parser.execute('echo abaabbccc')
        self.assertEqual(self._output, (('abaabbccc',), {}))
        def invalid_token():
            parser.execute('echo asdf')
        self.assertRaises(InvalidToken, invalid_token)

    def test_lazy_evaluation(self):
        class Lazy(object): pass
        lazy = Lazy()

        xml = StringIO("""<?xml version="1.0"?>
        <grammar>
            <node name='echo'>
                <variable name='text'>
                    <action callback='a_local and lazy.echo(text)'/>
                </variable>
            </node>
        </grammar>
        """)

        grammar = XMLGrammar(xml)
        parser = Parser(grammar, data={
            'echo': self._echo,
            'lazy': lazy,
            'a_local': True,
            })
        lazy.echo = self._echo
        parser.execute('echo abaabbccc')
        self.assertEqual(self._output, (('abaabbccc',), {}))

    def test_attribute_aliases(self):
        xml = StringIO("""<?xml version="1.0"?>
        <grammar>
            <node if="echo_allowed" name='echo'>
                <variable name='text'>
                    <action exec='echo(text)'/>
                </variable>
            </node>
        </grammar>
        """)

        grammar = XMLGrammar(xml)
        parser = Parser(grammar, data={
            'echo': self._echo,
            'echo_allowed': True,
            })
        parser.execute('echo hello')
        self.assertEqual(self._output, (('hello',), {}))

    def test_cast_attribute(self):
        class Test(Node):
            @classmethod
            def cast_attribute(cls, namespace, name, value):
                if name == 'test':
                    return int(value), {}
                return value, {}

        xml = StringIO("""<?xml version="1.0"?>
        <grammar>
            <test test="10" name="test">
            </test>
        </grammar>
        """)
        grammar = XMLGrammar(xml, extra_nodes=[Test])
        self.assertTrue(isinstance(grammar.find('/test').test, int))

    def test_attribute_aliases(self):
        class Parent(Node):
            @classmethod
            def attribute_aliases(cls):
                return {'foo': 'bar'}

        class Test(Parent):
            @classmethod
            def attribute_aliases(cls):
                return {'baz': 'waz'}

        xml = StringIO("""<?xml version="1.0"?>
        <grammar>
            <test baz="10" foo="20" name="test">
            </test>
        </grammar>
        """)
        grammar = XMLGrammar(xml, extra_nodes=[Test])
        node = grammar.find('/test')
        self.assertTrue(node.bar, '10')
        self.assertTrue(node.waz, '20')

    def test_set_cast(self):
        xml = StringIO("""<?xml version="1.0"?>
        <grammar>
            <defaults baz="10" foo="20" waz="'waz'">
                <node name="test"></node>
            </defaults>
        </grammar>
        """)
        parser = Parser(XMLGrammar(xml))
        self.assertEqual(parser.parse('test').vars,
                         {'foo': 20, 'baz': 10, 'waz': 'waz'})

def suite():
    import cly
    import cly.interactive
    import cly.console
    import cly.parser
    import cly.builder
    import cly.exceptions

    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestXMLGrammar, 'test'))
    suite.addTest(doctest.DocTestSuite(cly))
    suite.addTest(doctest.DocTestSuite(cly.interactive))
    suite.addTest(doctest.DocTestSuite(cly.console))
    suite.addTest(doctest.DocTestSuite(cly.parser))
    suite.addTest(doctest.DocTestSuite(cly.builder))
    suite.addTest(doctest.DocTestSuite(cly.exceptions))
    suite.addTest(doctest.DocFileSuite('../doc/guide.rst'))
    suite.addTest(doctest.DocFileSuite('../doc/tutorial.rst'))

    return suite


if __name__ == '__main__':
    unittest.main(defaultTest='suite')
