from __future__ import unicode_literals
import ast
import asttokens
import io
import os
import sys
import unittest

def get_fixture_path(*path_parts):
  python_dir = 'python%s' % sys.version_info[0]
  return os.path.join(os.path.dirname(__file__), "testdata", python_dir, *path_parts)

def read_fixture(*path_parts):
  with io.open(get_fixture_path(*path_parts), "r", newline="\n") as f:
    return f.read()

def collect_nodes_preorder(root):
  nodes = []
  def append(node, par_value):
    nodes.append(node)
    return (None, None)
  asttokens.util.visit_tree(root, append, None)
  return nodes


class TestMarkTokens(unittest.TestCase):

  def test_assign_first_tokens(self):
    source = read_fixture('astroid', 'module.py')
    root = ast.parse(source)
    atok = asttokens.ASTTokens(source)
    atok.mark_tokens(root)
    all_nodes = collect_nodes_preorder(root)

    def get_node_types_at(line, col):
      token = atok.get_token(line, col)
      return {n.__class__.__name__ for n in all_nodes if n.first_token == token}

    # Line 14 is: [indent 4] MY_DICT[key] = val
    self.assertEqual(get_node_types_at(14, 4), {'Name', 'Subscript', 'Assign'})

    # Line 35 is: [indent 12] raise XXXError()
    self.assertEqual(get_node_types_at(35, 12), {'Raise'})
    self.assertEqual(get_node_types_at(35, 18), {'Call', 'Name'})

    # Line 53 is: [indent 12] autre = [a for (a, b) in MY_DICT if b]
    self.assertEqual(get_node_types_at(53, 20), {'ListComp'})
    self.assertEqual(get_node_types_at(53, 21), {'Name'})
    self.assertEqual(get_node_types_at(53, 23), {'comprehension'})

    # Line 59 is: [indent 12] global_access(local, val=autre)
    self.assertEqual(get_node_types_at(59, 12), {'Name', 'Call', 'Expr'})
    self.assertEqual(get_node_types_at(59, 26), {'Name'})
    self.assertEqual(get_node_types_at(59, 37), {'Name', 'keyword'})

  def test_mark_tokens_simple(self):
    source = read_fixture('astroid', 'module.py')
    root = ast.parse(source)
    atok = asttokens.ASTTokens(source)
    atok.mark_tokens(root)
    all_nodes = collect_nodes_preorder(root)

    def get_node_text(line, col, type_name):
      token = atok.get_token(line, col)
      for n in all_nodes:
        if n.first_token == token and n.__class__.__name__ == type_name:
          return atok.get_text(n)

    # Line 14 is: [indent 4] MY_DICT[key] = val
    self.assertEqual(get_node_text(14, 4, 'Name'), 'MY_DICT')
    self.assertEqual(get_node_text(14, 4, 'Subscript'), 'MY_DICT[key]')
    self.assertEqual(get_node_text(14, 4, 'Assign'), 'MY_DICT[key] = val')

    # Line 35 is: [indent 12] raise XXXError()
    self.assertEqual(get_node_text(35, 12, 'Raise'), 'raise XXXError()')
    self.assertEqual(get_node_text(35, 18, 'Call'), 'XXXError()')
    self.assertEqual(get_node_text(35, 18, 'Name'), 'XXXError')

    # Line 53 is: [indent 12] autre = [a for (a, b) in MY_DICT if b]
    self.assertEqual(get_node_text(53, 20, 'ListComp'), '[a for (a, b) in MY_DICT if b]')
    self.assertEqual(get_node_text(53, 21, 'Name'), 'a')

  def test_mark_tokens_multiline(self):
    source = (
"""(    # line1
a,      # line2
b +     # line3
  c +   # line4
  d     # line5
)""")
    root = ast.parse(source)
    atok = asttokens.ASTTokens(source)
    atok.mark_tokens(root)

    all_nodes = {atok.get_text(node) for node in ast.walk(root)}
    self.assertEqual(all_nodes, {
      '',             # nodes we don't care about
      source,
      'a', 'b', 'c', 'd',
      # All other expressions preserve newlines and comments but are parenthesized.
      'b +     # line3\n  c',
      'b +     # line3\n  c +   # line4\n  d',
      'a,      # line2\nb +     # line3\n  c +   # line4\n  d',
    })
