import ast
import sys
import unittest

from asttokens import ASTText, supports_tokenless
from asttokens.util import fstring_positions_work

source = """
x = 1
if x > 0:
  for i in range(10):
    print(i)
else:
  print('negative')

def foo(bar):
  pass

print(f"{xx + 22} is negative {1.23:.2f} {'a'!r} {yy =} {aa:{bb}}")

import a
import b as c, d.e as f
from foo.bar import baz as spam
"""

fstring_node_dumps = [
  ast.dump(ast.parse(s).body[0].value)  # type: ignore
  for s in ["xx", "yy", "aa", "bb", "xx + 22", "22", "1.23", "'a'"]
]


def is_fstring_internal_node(node):
  """
  Returns True if the given node is an internal node in an f-string.
  Only applies for nodes parsed from the source above.
  """
  return ast.dump(node) in fstring_node_dumps


def is_fstring_format_spec(node):
  """
  Returns True if the given node is a format specifier in an f-string.
  Only applies for nodes parsed from the source above.
  """
  return (
      isinstance(node, ast.JoinedStr)
      and len(node.values) == 1
      and (
          (
              isinstance(node.values[0], ast.Str)
              and node.values[0].value in ['.2f']
          ) or (
              isinstance(node.values[0], ast.FormattedValue)
              and isinstance(node.values[0].value, ast.Name)
              and node.values[0].value.id == 'bb'
          )
      )
  )


@unittest.skipUnless(supports_tokenless(), "Python version does not support not using tokens")
class TestTokenless(unittest.TestCase):
  def test_get_text_tokenless(self):
    atok = ASTText(source)

    for node in ast.walk(atok.tree):
      if not isinstance(node, (ast.arguments, ast.arg)):
        self.check_node(atok, node)
        self.assertTrue(supports_tokenless(node), node)

    # Check that we didn't need to fall back to using tokens
    self.assertIsNone(atok._asttokens)

    has_tokens = False
    for node in ast.walk(atok.tree):
      self.check_node(atok, node)

      if isinstance(node, ast.arguments):
        has_tokens = True

      self.assertEqual(atok._asttokens is not None, has_tokens)

    # Now we have started using tokens as fallback
    self.assertIsNotNone(atok._asttokens)
    self.assertTrue(has_tokens)

  def check_node(self, atok, node):
    if not hasattr(node, 'lineno'):
      self.assertEqual(ast.get_source_segment(source, node), None)
      atok_text = atok.get_text(node)
      if not isinstance(node, (ast.arg, ast.arguments)):
        self.assertEqual(atok_text, source if isinstance(node, ast.Module) else '', node)
      return

    for padded in [True, False]:
      ast_text = ast.get_source_segment(source, node, padded=padded)
      atok_text = atok.get_text(node, padded=padded)
      if ast_text:
        if sys.version_info < (3, 12) and (
          ast_text.startswith("f") and isinstance(node, (ast.Str, ast.FormattedValue))
          or is_fstring_format_spec(node)
          or (not fstring_positions_work() and is_fstring_internal_node(node))
        ):
          self.assertEqual(atok_text, "", node)
        else:
          self.assertEqual(atok_text, ast_text, node)
          self.assertEqual(
            atok.get_text_positions(node, padded=False),
            (
              (node.lineno, node.col_offset),
              (node.end_lineno, node.end_col_offset),
            ),
          )

  def test_nested_fstrings(self):
    f1 = 'f"a {1+2} b {3+4} c"'
    f2 = "f'd {" + f1 + "} e'"
    f3 = "f'''{" + f2 + "}{" + f1 + "}'''"
    f4 = 'f"""{' + f3 + '}"""'
    s = 'f = ' + f4
    atok = ASTText(s)
    self.assertEqual(atok.get_text(atok.tree), s)
    n4 = atok.tree.body[0].value
    n3 = n4.values[0].value
    n2 = n3.values[0].value
    n1 = n2.values[1].value
    self.assertEqual(atok.get_text(n4), f4)
    if fstring_positions_work():
      self.assertEqual(atok.get_text(n3), f3)
      self.assertEqual(atok.get_text(n2), f2)
      self.assertEqual(atok.get_text(n1), f1)
    else:
      self.assertEqual(atok.get_text(n3), '')
      self.assertEqual(atok.get_text(n2), '')
      self.assertEqual(atok.get_text(n1), '')


class TestFstringPositionsWork(unittest.TestCase):
  def test_fstring_positions_work(self):
    self.assertEqual(
      fstring_positions_work() and supports_tokenless(),
      sys.version_info >= (3, 10, 6),
    )
