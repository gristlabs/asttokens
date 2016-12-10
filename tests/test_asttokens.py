# -*- coding: UTF-8 -*-
from __future__ import unicode_literals, print_function
import ast
import six
import token
import unittest
from .context import asttokens
from . import tools

class TestASTTokens(unittest.TestCase):

  def test_tokenizing(self):
    # Test that we produce meaningful tokens on initialization.
    source = "import re  # comment\n\nfoo = 'bar'\n"
    atok = asttokens.ASTTokens(source)
    self.assertEqual(atok.text, source)
    self.assertEqual([str(t) for t in atok.tokens], [
      "NAME:'import'",
      "NAME:'re'",
      "COMMENT:'# comment'",
      "NEWLINE:'\\n'",
      "NL:'\\n'",
      "NAME:'foo'",
      "OP:'='",
      'STRING:"\'bar\'"',
      "NEWLINE:'\\n'",
      "ENDMARKER:''"
    ])

    self.assertEqual(atok.tokens[5].type, token.NAME)
    self.assertEqual(atok.tokens[5].string, 'foo')
    self.assertEqual(atok.tokens[5].index, 5)
    self.assertEqual(atok.tokens[5].startpos, 22)
    self.assertEqual(atok.tokens[5].endpos, 25)


  def test_token_methods(self):
    # Test the methods that deal with tokens: prev/next_token, get_token, get_token_from_offset.
    source = "import re  # comment\n\nfoo = 'bar'\n"
    atok = asttokens.ASTTokens(source)
    self.assertEqual(str(atok.tokens[3]), "NEWLINE:'\\n'")
    self.assertEqual(str(atok.tokens[4]), "NL:'\\n'")
    self.assertEqual(str(atok.tokens[5]), "NAME:'foo'")
    self.assertEqual(str(atok.tokens[6]), "OP:'='")
    self.assertEqual(atok.prev_token(atok.tokens[5]), atok.tokens[3])
    self.assertEqual(atok.prev_token(atok.tokens[5], include_extra=True), atok.tokens[4])
    self.assertEqual(atok.next_token(atok.tokens[5]), atok.tokens[6])
    self.assertEqual(atok.next_token(atok.tokens[1]), atok.tokens[3])
    self.assertEqual(atok.next_token(atok.tokens[1], include_extra=True), atok.tokens[2])

    self.assertEqual(atok.get_token_from_offset(21), atok.tokens[4])
    self.assertEqual(atok.get_token_from_offset(22), atok.tokens[5])
    self.assertEqual(atok.get_token_from_offset(23), atok.tokens[5])
    self.assertEqual(atok.get_token_from_offset(24), atok.tokens[5])
    self.assertEqual(atok.get_token_from_offset(25), atok.tokens[5])
    self.assertEqual(atok.get_token_from_offset(26), atok.tokens[6])

    self.assertEqual(atok.get_token(2, 0), atok.tokens[4])
    self.assertEqual(atok.get_token(3, 0), atok.tokens[5])
    self.assertEqual(atok.get_token(3, 1), atok.tokens[5])
    self.assertEqual(atok.get_token(3, 2), atok.tokens[5])
    self.assertEqual(atok.get_token(3, 3), atok.tokens[5])
    self.assertEqual(atok.get_token(3, 4), atok.tokens[6])

    self.assertEqual(list(atok.token_range(atok.tokens[4], atok.tokens[6], include_extra=True)),
                     atok.tokens[4:7])


  def test_to_source(self):
    # Verify that to_source() actually works, with a coulpe of cases that have caused hiccups.
    source = "foo(a, b, *d, c=2, **e)"
    root = ast.parse(source)
    self.assertEqual(tools.to_source(root.body[0]), source)

    source = 'def foo():\n    """xxx"""\n    None'
    root = ast.parse(source).body[0]
    self.assertEqual(tools.to_source(root).strip(), source)


  def test_unicode_offsets(self):
    # ast modules provides utf8 offsets, while tokenize uses unicode offsets. Make sure we
    # translate correctly.
    source = "foo('фыва',a,b)"
    atok = asttokens.ASTTokens(source)
    self.assertEqual([six.text_type(t) for t in atok.tokens], [
      "NAME:'foo'",
      "OP:'('",
      'STRING:"%s"' % repr('фыва').lstrip('u'),
      "OP:','",
      "NAME:'a'",
      "OP:','",
      "NAME:'b'",
      "OP:')'",
      "ENDMARKER:''"
    ])
    self.assertEqual(atok.tokens[2].startpos, 4)
    self.assertEqual(atok.tokens[2].endpos, 10)      # Counting characters, not bytes
    self.assertEqual(atok.tokens[4].startpos, 11)
    self.assertEqual(atok.tokens[4].endpos, 12)
    self.assertEqual(atok.tokens[6].startpos, 13)
    self.assertEqual(atok.tokens[6].endpos, 14)

    root = ast.parse(source)

    # Verify that ast parser produces offsets as we expect. This is just to inform the
    # implementation.
    string_node = next(n for n in ast.walk(root) if isinstance(n, ast.Str))
    self.assertEqual(string_node.lineno, 1)
    self.assertEqual(string_node.col_offset, 4)

    a_node = next(n for n in ast.walk(root) if isinstance(n, ast.Name) and n.id == 'a')
    self.assertEqual((a_node.lineno, a_node.col_offset), (1, 15))   # Counting bytes, not chars.

    b_node = next(n for n in ast.walk(root) if isinstance(n, ast.Name) and n.id == 'b')
    self.assertEqual((b_node.lineno, b_node.col_offset), (1, 17))

    # Here we verify that we use correct offsets (translating utf8 to unicode offsets) when
    # extracting text ranges.
    atok.mark_tokens(root)
    self.assertEqual(atok.get_text(string_node), "'фыва'")
    self.assertEqual(atok.get_text(a_node), "a")
    self.assertEqual(atok.get_text(b_node), "b")


if __name__ == "__main__":
  unittest.main()
