# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function

import re

import astroid
from . import tools, test_mark_tokens


class TestAstroid(test_mark_tokens.TestMarkTokens):

  is_astroid_test = True
  module = astroid

  @classmethod
  def create_mark_checker(cls, source):
    builder = astroid.builder.AstroidBuilder()
    tree = builder.string_build(source)
    return tools.MarkChecker(source, tree=tree)

  def assert_nodes_equal(self, node1, node2):
    self.assertEqual(
      repr_tree(node1),
      repr_tree(node2),
    )


def repr_tree(node):
  result = node.repr_tree()
  result = result.replace('AssignName(name=', 'Name(name=')
  result = result.replace('DelName(name=', 'Name(name=')
  result = re.sub(r'(AssignAttr|DelAttr)(\(\s*attrname=)', r'Attribute\2', result)
  result = re.sub(r'ctx=<Context\.(Store: 2|Del: 3)>', r'ctx=<Context.Load: 1>', result)

  # Weird bug in astroid that collapses spaces in docstrings sometimes maybe
  result = re.sub(r"' +\\n'", r"'\\n'", result)

  return result
