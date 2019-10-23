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
  """
  Returns a canonical string representation of an astroid node
  normalised to ignore the context of each node which can change when parsing
  substrings of source code.

  E.g. "a" is a Name in expression "a + 1" and is an AssignName in expression "a = 1",
  but we don't care about this difference when comparing structure and content.
  """
  result = node.repr_tree()

  # astroid represents context in multiple ways
  # Convert Store and Del contexts to Load
  # Similarly convert Assign/Del Name/Attr to just Name/Attribute (i.e. Load)
  result = re.sub(r'(AssignName|DelName)(\(\s*name=)', r'Name\2', result)
  result = re.sub(r'(AssignAttr|DelAttr)(\(\s*attrname=)', r'Attribute\2', result)
  result = re.sub(r'ctx=<Context\.(Store: 2|Del: 3)>', r'ctx=<Context.Load: 1>', result)

  # Weird bug in astroid that collapses spaces in docstrings sometimes maybe
  result = re.sub(r"' +\\n'", r"'\\n'", result)

  return result
