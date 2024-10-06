# -*- coding: utf-8 -*-
import astroid

from asttokens import ASTTokens
from asttokens.astroid_compat import astroid_node_classes
from . import test_mark_tokens


class TestAstroid(test_mark_tokens.TestMarkTokens):

  is_astroid_test = True
  astroid_version = int(astroid.__version__.split('.')[0])
  module = astroid

  nodes_classes = astroid_node_classes.NodeNG
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
    fields = node._astroid_fields + node._other_fields
    for field in fields:
      if field == 'ctx':
        continue
      if field == 'doc' and 'doc_node' in fields:
        continue
      yield field, getattr(node, field)

  @staticmethod
  def create_asttokens(source):
    builder = astroid.builder.AstroidBuilder()
    try:
      tree = builder.string_build(source)
    except AttributeError as e:
      raise AstroidTreeException(str(e))
    return ASTTokens(source, tree=tree)


class AstroidTreeException(Exception):
  pass
