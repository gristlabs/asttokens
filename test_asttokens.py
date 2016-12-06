import asttokens
import os
import token
import unittest


class TestLineNumbers(unittest.TestCase):
  def test_linenumbers(self):
    ln = asttokens.LineNumbers("Hello\nworld\nThis\n\nis\n\na test.\n")
    self.assertEqual(ln.line_to_offset(1, 0), 0)
    self.assertEqual(ln.line_to_offset(1, 5), 5)
    self.assertEqual(ln.line_to_offset(2, 0), 6)
    self.assertEqual(ln.line_to_offset(2, 5), 11)
    self.assertEqual(ln.line_to_offset(3, 0), 12)
    self.assertEqual(ln.line_to_offset(4, 0), 17)
    self.assertEqual(ln.line_to_offset(5, 0), 18)
    self.assertEqual(ln.line_to_offset(6, 0), 21)
    self.assertEqual(ln.line_to_offset(7, 0), 22)
    self.assertEqual(ln.line_to_offset(7, 7), 29)
    self.assertEqual(ln.offset_to_line(0),  (1, 0))
    self.assertEqual(ln.offset_to_line(5),  (1, 5))
    self.assertEqual(ln.offset_to_line(6),  (2, 0))
    self.assertEqual(ln.offset_to_line(11), (2, 5))
    self.assertEqual(ln.offset_to_line(12), (3, 0))
    self.assertEqual(ln.offset_to_line(17), (4, 0))
    self.assertEqual(ln.offset_to_line(18), (5, 0))
    self.assertEqual(ln.offset_to_line(21), (6, 0))
    self.assertEqual(ln.offset_to_line(22), (7, 0))
    self.assertEqual(ln.offset_to_line(29), (7, 7))

    # Test that out-of-bounds inputs still return something sensible.
    self.assertEqual(ln.line_to_offset(6, 19), 30)
    self.assertEqual(ln.line_to_offset(100, 99), 30)
    self.assertEqual(ln.line_to_offset(2, -1), 6)
    self.assertEqual(ln.line_to_offset(-1, 99), 0)
    self.assertEqual(ln.offset_to_line(30), (8, 0))
    self.assertEqual(ln.offset_to_line(100), (8, 0))
    self.assertEqual(ln.offset_to_line(-100), (1, 0))

class TestCodeText(unittest.TestCase):

  def test_codetext_simple(self):
    source = "import re  # comment\n\nfoo = 'bar'\n"
    ctext = asttokens.CodeText(source)
    self.assertEqual(ctext.text, source)
    self.assertEqual([str(t) for t in ctext.tokens], [
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

    self.assertEqual(ctext.tokens[5].type, token.NAME)
    self.assertEqual(ctext.tokens[5].string, 'foo')
    self.assertEqual(ctext.tokens[5].index, 5)
    self.assertEqual(ctext.tokens[5].startpos, 22)
    self.assertEqual(ctext.tokens[5].endpos, 25)

  def test_codetext_methods(self):
    source = "import re  # comment\n\nfoo = 'bar'\n"
    ctext = asttokens.CodeText(source)
    self.assertEqual(str(ctext.tokens[5]), "NAME:'foo'")
    self.assertEqual(str(ctext.next_token(ctext.tokens[5])), "OP:'='")
    self.assertEqual(str(ctext.prev_token(ctext.tokens[5])), "NL:'\\n'")
    self.assertEqual(ctext.get_token(21), ctext.tokens[4])
    self.assertEqual(ctext.get_token(22), ctext.tokens[5])
    self.assertEqual(ctext.get_token(23), ctext.tokens[5])
    self.assertEqual(ctext.get_token(24), ctext.tokens[5])
    self.assertEqual(ctext.get_token(25), ctext.tokens[5])
    self.assertEqual(ctext.get_token(26), ctext.tokens[6])
    self.assertEqual([str(t) for t in ctext.token_range(ctext.tokens[4], ctext.tokens[6])],
                     ["NL:'\\n'", "NAME:'foo'", "OP:'='"])

#def get_fixture_path(fixture_name):
#  return os.path.join(os.path.dirname(__file__), "fixtures", fixture_name)


if __name__ == "__main__":
  unittest.main()
