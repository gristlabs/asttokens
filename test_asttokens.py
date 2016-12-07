import ast
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
    self.assertEqual(str(ctext.tokens[3]), "NEWLINE:'\\n'")
    self.assertEqual(str(ctext.tokens[4]), "NL:'\\n'")
    self.assertEqual(str(ctext.tokens[5]), "NAME:'foo'")
    self.assertEqual(str(ctext.tokens[6]), "OP:'='")
    self.assertEqual(ctext.prev_token(ctext.tokens[5]), ctext.tokens[3])
    self.assertEqual(ctext.prev_token(ctext.tokens[5], include_extra=True), ctext.tokens[4])
    self.assertEqual(ctext.next_token(ctext.tokens[5]), ctext.tokens[6])
    self.assertEqual(ctext.next_token(ctext.tokens[1]), ctext.tokens[3])
    self.assertEqual(ctext.next_token(ctext.tokens[1], include_extra=True), ctext.tokens[2])

    self.assertEqual(ctext.get_token_from_offset(21), ctext.tokens[4])
    self.assertEqual(ctext.get_token_from_offset(22), ctext.tokens[5])
    self.assertEqual(ctext.get_token_from_offset(23), ctext.tokens[5])
    self.assertEqual(ctext.get_token_from_offset(24), ctext.tokens[5])
    self.assertEqual(ctext.get_token_from_offset(25), ctext.tokens[5])
    self.assertEqual(ctext.get_token_from_offset(26), ctext.tokens[6])

    self.assertEqual(ctext.get_token(2, 0), ctext.tokens[4])
    self.assertEqual(ctext.get_token(3, 0), ctext.tokens[5])
    self.assertEqual(ctext.get_token(3, 1), ctext.tokens[5])
    self.assertEqual(ctext.get_token(3, 2), ctext.tokens[5])
    self.assertEqual(ctext.get_token(3, 3), ctext.tokens[5])
    self.assertEqual(ctext.get_token(3, 4), ctext.tokens[6])

    self.assertEqual(list(ctext.token_range(ctext.tokens[4], ctext.tokens[6], include_extra=True)),
                     ctext.tokens[4:7])


class TestAssignTokensVisitor(unittest.TestCase):

  #def test_simple_code(self):
  #  source = "import re  # comment\n\nfoo = 'bar'\n"
  #  root = ast.parse(source)
  #  ast.fix_missing_locations(root)
  #  code = asttokens.CodeText(source)
  #  asttokens.assign_first_tokens(root, code)
  #  for node in ast.walk(root):
  #    print "NODE %s:%s %s %s" % (
  #      getattr(node, 'lineno', None),
  #      getattr(node, 'col_offset', None),
  #      getattr(node, 'first_token', None),
  #      ast.dump(node, True, True))
  #    #print "  %r" % asttokens.get_text(node, source)

  #  # asttokens.AssignLastToken(code).visit(root)
  #  # for node in ast.walk(root):
  #  #   print "NODE %s:%s %s-%s %s" % (
  #  #     getattr(node, 'lineno', None),
  #  #     getattr(node, 'col_offset', None),
  #  #     getattr(node, 'first_token', None),
  #  #     getattr(node, 'last_token', None),
  #  #     ast.dump(node, True, True))
  #  #   print "  %r" % asttokens.get_text(node, source)

  #  # #code.mark_tokens(root)

  #def test_more(self):
  #  source = read_fixture('astroid', 'module2.py')
  #  root = ast.parse(source)
  #  print repr(root)
  #  code = asttokens.CodeText(source)
  #  asttokens.assign_first_tokens(root, code)

  #  print source
  #  for node in asttokens.walk(root):
  #    #if isinstance(node, (ast.NAME, ast.STRING)):
  #    #  continue
  #    if getattr(node, 'lineno', None):
  #      print "LINE", source.splitlines()[getattr(node, 'lineno', None) - 1]
  #    print "NODE %s:%s %s %s" % (
  #      getattr(node, 'lineno', None),
  #      getattr(node, 'col_offset', None),
  #      getattr(node, 'first_token', None),
  #      repr(node))#ast.dump(node, True, True))


  def test_assign_first_tokens(self):
    source = read_fixture('astroid', 'module.py')
    root = ast.parse(source)
    code = asttokens.CodeText(source)
    code.mark_tokens(root)
    all_nodes = list(asttokens.walk(root))

    def get_node_types_at(line, col):
      token = code.get_token(line, col)
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

  def test_mark_tokens(self):
    source = read_fixture('astroid', 'module.py')
    root = ast.parse(source)
    code = asttokens.CodeText(source)
    code.mark_tokens(root)
    all_nodes = list(asttokens.walk(root))

    def get_node_text(line, col, type_name):
      token = code.get_token(line, col)
      for n in all_nodes:
        if n.first_token == token and n.__class__.__name__ == type_name:
          return asttokens.get_text(n, source)

    # Line 35 is: [indent 12] raise XXXError()
    self.assertEqual(get_node_text(35, 12, 'Raise'), 'raise XXXError()')

# TODO
# - Fix borken test
# - Add a few checks to test_mark_tokens -- rename to _simple
# - Add more generic test: for each node, if expr or stmt, try to recreate and compare outputs.


def get_fixture_path(*path_parts):
  return os.path.join(os.path.dirname(__file__), "fixtures", *path_parts)

def read_fixture(*path_parts):
  with open(get_fixture_path(*path_parts), "rb") as f:
    return f.read()


if __name__ == "__main__":
  unittest.main()
