from __future__ import unicode_literals, print_function
import ast
import astroid
import asttokens
import copy
import io
import os
import re
import sys
from asttokens import util


def get_fixture_path(*path_parts):
  python_dir = 'python%s' % sys.version_info[0]
  return os.path.join(os.path.dirname(__file__), "testdata", python_dir, *path_parts)

def read_fixture(*path_parts):
  with io.open(get_fixture_path(*path_parts), "r", newline="\n") as f:
    return f.read()


def _parse_stmt(text):
  # ast.parse produces a module, but we here want to produce a single statement.
  return ast.parse(text, 'exec').body[0]

def parse_snippet(text, is_expr=False, is_module=False):
  """
  Returns the parsed AST tree for the given text, handling issues with indentation and newlines
  when text is really an extracted part of larger code.
  """
  # If text is indented, it's a statement, and we need to put in a scope for indents to be valid
  # (using textwrap.dedent is insufficient because some lines may not indented, e.g. comments or
  # multiline strings). If text is an expression but has newlines, we parenthesize it to make it
  # parsable.
  indented = re.match(r'^[ \t]+\S', text)
  if indented:
    return _parse_stmt('def dummy():\n' + text).body[0]
  elif is_expr:
    return _parse_stmt('(' + text + ')').value
  elif is_module:
    return ast.parse(text, 'exec')
  else:
    return _parse_stmt(text)


def to_source(node):
  """
  Convert a node to source code by converting it to an astroid tree first, and using astroid's
  as_string() method.
  """
  if hasattr(node, 'as_string'):
    return node.as_string()

  builder = astroid.rebuilder.TreeRebuilder(astroid.manager.AstroidManager())
  # We need to make a deep copy of node; not sure why, but node seems affected by the astroid
  # TreeRebuilder.
  node_copy = copy.deepcopy(node)
  if isinstance(node, ast.Module):
    anode = builder.visit_module(node_copy, '', '', '')
  else:
    # Anything besides Module needs to have astroid Module passed in as a parent.
    amodule = astroid.nodes.Module('', None)
    anode = builder.visit(node_copy, amodule)
  return anode.as_string()


def collect_nodes_preorder(root):
  """Returns a list of all nodes using pre-order traversal (i.e. parent before children)."""
  nodes = []
  def append(node, par_value):
    nodes.append(node)
    return (None, None)
  util.visit_tree(root, append, None)
  return nodes


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
    return "%s:%s" % (node.__class__.__name__, self.atok.get_text(node))

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

      if isinstance(node, astroid.nodes.Yield):
        # Astroid stringifies Yield nodes differently depending on parent, so these are too
        # annoying to verify.
        continue

      text = self.atok.get_text(node)
      rebuilt_node = parse_snippet(text, is_expr=util.is_expr(node), is_module=util.is_module(node))

      # Now we need to check if the two nodes are equivalent.
      test_case.assertEqual(to_source(rebuilt_node), to_source(node))
      tested_nodes += 1

    return tested_nodes
