from __future__ import unicode_literals, print_function
import ast
import io
import os
import re
import sys

import astroid
import asttokens
from asttokens import util

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
  def __init__(self, source, parse=False, tree=None):
    self.atok = asttokens.ASTTokens(source, parse=parse, tree=tree)
    self.all_nodes = collect_nodes_preorder(self.atok.tree)

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
    tested_nodes = 0
    for node in self.all_nodes:
      if not (util.is_stmt(node) or util.is_expr(node) or util.is_module(node)):
        continue

      text = self.atok.get_text(node)

      # `elif:` is really just `else: if:` to the AST,
      # so get_text can return text starting with elif when given an If node.
      # This is generally harmless and there's probably no good alternative,
      # but in isolation it's invalid syntax
      text = re.sub(r'^(\s*)elif(\W)', r'\1if\2', text, re.MULTILINE)

      rebuilt_node = test_case.parse_snippet(text, node)
      test_case.assert_nodes_equal(node, rebuilt_node)
      tested_nodes += 1

    return tested_nodes


