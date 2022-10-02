import ast
import unittest

from asttokens import asttokens, supports_unmarked

source = """
x = 1
if x > 0:
  for i in range(10):
    print(i)
else:
  print('negative')

def foo(bar):
  pass

print(f"{x + 2} is negative {1.23:.2f} {'a':!r} {x =}")

import a
import b as c, d.e as f
from foo.bar import baz as spam
"""


@unittest.skipUnless(supports_unmarked(), "Python version does not support unmarked nodes")
class TestUmarked(unittest.TestCase):
  def test_unmarked(self):
    atok = asttokens.ASTTokens(source, parse=True, init_tokens=False)
    for node in ast.walk(atok.tree):
      if isinstance(node, (ast.arguments, ast.arg)):
        continue

      self.assertTrue(supports_unmarked(node), node)

      if not hasattr(node, 'lineno'):
        self.assertEqual(ast.get_source_segment(source, node), None)
        self.assertEqual(atok.get_text(node), source if isinstance(node, ast.Module) else '')
        continue

      self.assertEqual(
        atok.get_text_positions(node, padded=False),
        (
          (node.lineno, node.col_offset),
          (node.end_lineno, node.end_col_offset),
        ),
      )

      for padded in [True, False]:
        self.assertEqual(
          atok.get_text(node, padded=padded),
          ast.get_source_segment(source, node, padded=padded),
          node
        )

    self.assertIsNone(atok._tokens)

    has_tokens = False
    for node in ast.walk(atok.tree):
      atok_text = atok.get_text(node, padded=True)
      ast_text = ast.get_source_segment(source, node, padded=True)
      if ast_text:
        self.assertEqual(atok_text, ast_text, node)

      if isinstance(node, ast.arguments):
        has_tokens = True

      self.assertEqual(atok._tokens is not None, has_tokens)
      self.assertEqual(atok._tokens is not None, has_tokens)

      if has_tokens:
        getattr(atok, 'tokens')
      else:
        with self.assertRaises(AssertionError):
          getattr(atok, 'tokens')

    self.assertIsNotNone(atok._tokens)
    self.assertTrue(has_tokens)
