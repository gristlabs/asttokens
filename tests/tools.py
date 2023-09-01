from __future__ import unicode_literals, print_function

import ast
import io
import os
import re
import sys

import astroid

from asttokens import util, supports_tokenless, ASTText


def get_fixture_path(*path_parts):
  python_dir = 'python%s' % sys.version_info[0]
  return os.path.join(os.path.dirname(__file__), "testdata", python_dir, *path_parts)

def read_fixture(*path_parts):
  with io.open(get_fixture_path(*path_parts), "r", newline="\n") as f:
    return f.read()


def collect_nodes_preorder(root):
  """Returns a list of all nodes using pre-order traversal (i.e. parent before children)."""
  nodes = []
  def append(node, par_value):    # pylint: disable=unused-argument
    nodes.append(node)
    return (None, None)
  util.visit_tree(root, append, None)
  return nodes

def get_node_name(node):
   name = node.__class__.__name__
   return 'Constant' if name in ('Num', 'Str', 'NameConstant') else name


class MarkChecker(object):
  """
  Helper tool to parse and mark an AST tree, with useful methods for verifying it.
  """
  def __init__(self, atok):
    self.atok = atok
    self.all_nodes = collect_nodes_preorder(self.atok.tree)
    self.atext = ASTText(atok.text, atok.tree, atok.filename)

  def get_nodes_at(self, line, col):
    """Returns all nodes that start with the token at the given position."""
    token = self.atok.get_token(line, col)
    return [n for n in self.all_nodes if n.first_token == token]

  def view_node(self, node):
    """Returns a representation of a node and its text, such as "Call:foo()". """
    return "%s:%s" % (get_node_name(node), self.atok.get_text(node))

  def view_nodes_at(self, line, col):
    """
    Returns a set of all node representations for nodes that start at the given position.
    E.g. {"Call:foo()", "Name:foo"}
    """
    return {self.view_node(n) for n in self.get_nodes_at(line, col)}

  def view_node_types_at(self, line, col):
    """
    Returns a set of all node types for nodes that start at the given position.
    E.g. {"Call", "Name"}
    """
    return {n.__class__.__name__ for n in self.get_nodes_at(line, col)}

  def verify_all_nodes(self, test_case):
    """
    Generically test atok.get_text() on the ast tree: for each statement and expression in the
    tree, we extract the text, parse it, and see if it produces an equivalent tree. Returns the
    number of nodes that were tested this way.
    """
    test_case.longMessage = True

    if supports_tokenless() and not test_case.is_astroid_test:
      num_supported = sum(supports_tokenless(n) for n in self.all_nodes)
      num_nodes = len(self.all_nodes)
      test_case.assertGreater(num_supported / num_nodes, 0.5, (num_supported, num_nodes))

    tested_nodes = 0
    for node in self.all_nodes:
      # slices currently only get the correct tokens/text for ast, not astroid.
      if util.is_slice(node) and test_case.is_astroid_test:
        continue

      text = self.atok.get_text(node)
      self.check_get_text_tokenless(node, test_case, text)

      if not (
          util.is_stmt(node) or
          util.is_expr(node) or
          util.is_module(node)):
        continue

      # await is not allowed outside async functions below 3.7
      # parsing again would give a syntax error
      if 'await' in text and 'async def' not in text and sys.version_info < (3, 7):
        continue

      # `elif:` is really just `else: if:` to the AST,
      # so get_text can return text starting with elif when given an If node.
      # This is generally harmless and there's probably no good alternative,
      # but in isolation it's invalid syntax
      text = re.sub(r'^(\s*)elif(\W)', r'\1if\2', text, re.MULTILINE)

      rebuilt_node = test_case.parse_snippet(text, node)

      try:
        test_case.assert_nodes_equal(node, rebuilt_node)
      except AssertionError:
        if test_case.is_astroid_test:
          # This can give a more helpful failure message with a diff
          test_case.assertEqual(
            repr_tree(node),
            repr_tree(rebuilt_node),
          )
        raise

      tested_nodes += 1

    return tested_nodes

  def check_get_text_tokenless(self, node, test_case, text):
    """
    Check that `text` (returned from get_text()) usually returns the same text
    whether from `ASTTokens` or `ASTText`.
    """

    if not supports_tokenless():
      return

    text_tokenless = self.atext.get_text(node)
    if isinstance(node, ast.alias):
      self._check_alias_tokenless(node, test_case, text_tokenless)
    elif util.is_module(node):
      test_case.assertEqual(text_tokenless, self.atext._text)
    elif isinstance(node, astroid.DictUnpack):
      # This is a strange node that *seems* to represent just the `**` in `{**foo}`
      # (not `**foo` or `foo`), but text_tokenless is `foo`
      # while `text` is just the first token of that.
      # 'Fixing' either of these or making them match doesn't seem useful.
      return
    elif isinstance(node, astroid.Decorators):
      # Another strange node where it's not worth making the two texts match
      return
    elif supports_tokenless(node):
      has_lineno = getattr(node, 'lineno', None) is not None
      test_case.assertEqual(has_lineno, text_tokenless != '')
      if has_lineno:
        if (
            text != text_tokenless
            and text_tokenless.startswith(text)
            and text_tokenless[len(text):].strip().startswith('# type: ')
            and test_case.is_astroid_test
        ):
          # astroid positions can include type comments, which we can ignore.
          return
        test_case.assertEqual(text, text_tokenless)
      else:
        # _get_text_positions_tokenless can't work with nodes without lineno.
        # Double-check that such nodes are unusual.
        test_case.assertFalse(util.is_stmt(node) or util.is_expr(node))
        if not test_case.is_astroid_test:
          with test_case.assertRaises(SyntaxError, msg=(text, ast.dump(node))):
            test_case.parse_snippet(text, node)

  def _check_alias_tokenless(self, node, test_case, text):
    if sys.version_info < (3, 10):
      # Before 3.10, aliases don't have position information
      test_case.assertEqual(text, '')
    # For 3.10+, ASTTokens.get_text often returns the wrong value for aliases.
    # So to verify ASTText.get_text, we instead check the general form.
    elif node.asname:
      test_case.assertEqual(text.split(), [node.name, 'as', node.asname])
    else:
      test_case.assertEqual(text, node.name)


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
