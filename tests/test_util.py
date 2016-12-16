# -*- coding: UTF-8 -*-
from __future__ import unicode_literals, print_function
import astroid
import unittest
from .context import asttokens

class TestUtil(unittest.TestCase):

  def print_timing(self):
    # pylint: disable=no-self-use
    # Test the implementation of asttokens.util.walk, which uses the same approach as
    # visit_tree(). This doesn't run as a normal unittest, but if you'd like to see timings, e.g.
    # after experimenting with the implementation, run this to see them:
    #
    #     nosetests -i print_timing -s tests.test_util
    #
    import timeit
    import textwrap
    setup = textwrap.dedent(
      '''
      import ast, asttokens
      source = "foo(bar(1 + 2), 'hello' + ', ' + 'world')"
      atok = asttokens.ASTTokens(source, parse=True)
      ''')
    print("ast", sorted(timeit.repeat(
      setup=setup, number=10000,
      stmt='len(list(ast.walk(atok.tree)))')))
    print("util", sorted(timeit.repeat(
      setup=setup, number=10000,
      stmt='len(list(asttokens.util.walk(atok.tree)))')))


  source = "foo(bar(1 + 2), 'hello' + ', ' + 'world')"

  def test_walk_ast(self):
    atok = asttokens.ASTTokens(self.source, parse=True)

    def view(node):
      return "%s:%s" % (node.__class__.__name__, atok.get_text(node))

    scan = [view(n) for n in asttokens.util.walk(atok.tree)]
    self.assertEqual(scan, [
      "Module:foo(bar(1 + 2), 'hello' + ', ' + 'world')",
      "Expr:foo(bar(1 + 2), 'hello' + ', ' + 'world')",
      "Call:foo(bar(1 + 2), 'hello' + ', ' + 'world')",
      'Name:foo',
      'Call:bar(1 + 2)',
      'Name:bar',
      'BinOp:1 + 2',
      'Num:1',
      'Num:2',
      "BinOp:'hello' + ', ' + 'world'",
      "BinOp:'hello' + ', '",
      "Str:'hello'",
      "Str:', '",
      "Str:'world'"
    ])

  def test_walk_astroid(self):
    atok = asttokens.ASTTokens(self.source, tree=astroid.builder.parse(self.source))

    def view(node):
      return "%s:%s" % (node.__class__.__name__, atok.get_text(node))

    scan = [view(n) for n in asttokens.util.walk(atok.tree)]
    self.assertEqual(scan, [
      "Module:foo(bar(1 + 2), 'hello' + ', ' + 'world')",
      "Expr:foo(bar(1 + 2), 'hello' + ', ' + 'world')",
      "Call:foo(bar(1 + 2), 'hello' + ', ' + 'world')",
      'Name:foo',
      'Call:bar(1 + 2)',
      'Name:bar',
      'BinOp:1 + 2',
      'Const:1',
      'Const:2',
      "BinOp:'hello' + ', ' + 'world'",
      "BinOp:'hello' + ', '",
      "Const:'hello'",
      "Const:', '",
      "Const:'world'"
    ])


if __name__ == "__main__":
  unittest.main()
