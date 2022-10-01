import ast
import unittest

from asttokens import asttokens, supports_unmarked

source = """
x = 1
if x > 0:
  def foo(bar):
    pass

  for i in range(10):
    print(i)
else:
  print(f"{x} is negative")
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
      atok.get_text(node, padded=True)

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
