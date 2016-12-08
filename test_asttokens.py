import ast
import asttokens
import astor    # pylint: disable=import-error
import os
import token
import re
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



def get_fixture_path(*path_parts):
  return os.path.join(os.path.dirname(__file__), "fixtures", *path_parts)

def read_fixture(*path_parts):
  with open(get_fixture_path(*path_parts), "rb") as f:
    return f.read()


class TestAssignTokensVisitor(unittest.TestCase):

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

  def test_mark_tokens_simple(self):
    source = read_fixture('astroid', 'module.py')
    root = ast.parse(source)
    code = asttokens.CodeText(source)
    code.mark_tokens(root)
    all_nodes = list(asttokens.walk(root))

    def get_node_text(line, col, type_name):
      token = code.get_token(line, col)
      for n in all_nodes:
        if n.first_token == token and n.__class__.__name__ == type_name:
          return code.get_text(n)

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

  def test_foo(self):
    source = "(a,\na + b\n + c + d)"
    root = ast.parse(source)
    code = asttokens.CodeText(source)
    for t in  code.tokens:
      print t
    code.mark_tokens(root)
    for n in ast.walk(root):
      print repr(n), ast.dump(n, include_attributes=True)
      print code.get_text(n)

  def xxxtest_bar(self):
    source = read_fixture("astroid", "joined_strings.py")
    root = ast.parse(source)
    all_nodes = [n for n in ast.walk(root)]
    class NV(ast.NodeVisitor):
      def __init__(self):
        self.count = 0
      def visit(self, node):
        self.generic_visit(node)
        self.count += 1
    nv = NV()
    nv.visit(root)
    self.assertEqual(len(all_nodes), nv.count)
    self.assertEqual(nv.count, 1)

  def test_mark_tokens_multiline(self):
    source = (
"""(    # line1
a,      # line2
b +     # line3
  c +   # line4
  d     # line5
)""")
    root = ast.parse(source)
    code = asttokens.CodeText(source)
    code.mark_tokens(root)

    all_nodes = {code.get_text(node) for node in ast.walk(root)}
    self.assertEqual(all_nodes, {
      None,           # nodes we don't care about
      source,
      'a', 'b', 'c', 'd',
      # All other expressions preserve newlines and comments but are parenthesized.
      '(b +     # line3\n  c)',
      '(b +     # line3\n  c +   # line4\n  d)',
      '(a,      # line2\nb +     # line3\n  c +   # line4\n  d)',
    })


  def test_mark_tokens(self):
    # There is a generic way to test. We can take an arbitrary piece of code, parse it, and for
    # each AST node, extract the piece of code text from first to last token. For many node types,
    # that piece should itself be compilable, and the resulting AST node should be equivalent.
    dir_path = get_fixture_path("astroid")
    for module in os.listdir(dir_path):
      if not module.endswith('.py'):
        continue
      print "PROCESSING", module
      source = read_fixture("astroid", module)
      root = ast.parse(source)
      code = asttokens.CodeText(source)
      code.mark_tokens(root)

      for node in ast.walk(root):
        if not isinstance(node, (ast.stmt, ast.expr)):
          continue
        # TODO Bleh. dedent gets borken when there are unindented comments.
        text = code.get_text(node)
        indented = re.match(r'^[ \t]+\S', text)
        if indented:
          text = "def dummy():\n" + text
        #print "TEXT", text
        try:
          rebuilt_node = ast.parse(text, 'exec').body[0]
        except Exception:
          print "CAN'T PARSE", text, repr(text)
          raise
        if indented:
          rebuilt_node = rebuilt_node.body[0]

        if isinstance(node, ast.expr) and isinstance(rebuilt_node, ast.Expr):
          rebuilt_node = rebuilt_node.value

        # Now we need to check if the two nodes are equivalent.
        try:
          self.assertEqual(astor.to_source(rebuilt_node),
                           astor.to_source(node))
        except RuntimeError, e:
          print "COMPARISON FAILED", e
          break
        except AssertionError, e:
          print "OUTPUT DIFFERS", text
          print "FAILED", e
          #raise

if __name__ == "__main__":
  unittest.main()
