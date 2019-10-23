# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function

import re

import astroid

from . import tools, test_mark_tokens


class TestAstroid(test_mark_tokens.TestMarkTokens):

  is_astroid_test = True
  module = astroid

  nodes_classes = astroid.ALL_NODE_CLASSES
  context_classes = [
    (astroid.Name, astroid.DelName, astroid.AssignName),
    (astroid.Attribute, astroid.DelAttr, astroid.AssignAttr),
  ]

  @staticmethod
  def iter_fields(node):
    """
    Yield a tuple of ``(fieldname, value)`` for each field
    that is present on *node*.

    Similar to ast.iter_fields, but for astroid and ignores context
    """
    for field in node._astroid_fields + node._other_fields:
      if field == 'ctx':
        continue
      yield field, getattr(node, field)

  @classmethod
  def create_mark_checker(cls, source):
    builder = astroid.builder.AstroidBuilder()
    tree = builder.string_build(source)
    return tools.MarkChecker(source, tree=tree)
