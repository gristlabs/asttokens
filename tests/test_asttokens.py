from __future__ import unicode_literals
import ast
import asttokens
import astor    # pylint: disable=import-error
import token
import re
import six
import unittest
from .test_mark_tokens import read_fixture, collect_nodes_preorder


def parse_snippet(text):
  """
  Returns the parsed AST tree for the given text, handling issues with indentation when text is
  really an extracted part of larger code.
  """
  # If text is indented, it's a statement, and we need to put in a scope for indents to be valid
  # (using textwrap.dedent is insufficient because some lines may not indented, e.g. comments or
  # multiline strings).
  indented = re.match(r'^[ \t]+\S', text)
  if indented:
    text = "def dummy():\n" + text

  try:
    module = ast.parse(text, 'exec')
  except SyntaxError as e:
    try:
      # If we can't parse it, maybe we can parse the parenthesized version. This will be the case
      # when the text is an expression that contains newlines but is missing enclosing parens.
      module = ast.parse('(' + text + ')', 'exec')
    except:
      raise e

  body = module.body[0]
  return body.body[0] if indented else body

def to_source(node):
  # We use astor to convert a node to source code (for verifying whether we got correct text
  # corresponding to a node). Unfortunately, astor has a bug with Call/ClassDef nodes in
  # python3.5+. We work around it here by adding missing starargs attributes to such nodes.
  if hasattr(ast, 'Starred'):
    for n in ast.walk(node):
      if isinstance(n, (ast.Call, ast.ClassDef)) and not hasattr(n, 'starargs'):
        # pylint: disable=no-member
        plain_args = n.args if isinstance(n, ast.Call) else n.bases
        n.starargs = next((arg.value for arg in plain_args if isinstance(arg, ast.Starred)), None)
        n.args = [arg for arg in plain_args if not isinstance(arg, ast.Starred)]
        n.kwargs = next((arg.value for arg in n.keywords if arg.arg is None), None)
        n.keywords = [arg for arg in n.keywords if arg.arg is not None]
  return astor.to_source(node)


class TestASTTokens(unittest.TestCase):

  def test_astor_fix(self):
    source = "foo(a, b, c=2, *d, **e)"
    root = ast.parse(source)
    self.assertEqual(to_source(root), source)

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


  def test_mark_tokens(self):
    # There is a generic way to test it. We can take an arbitrary piece of code, parse it, and for
    # each AST node, extract the corresponding code test. For nodes that are statements or
    # expressions, that piece should itself be compilable, and the resulting AST node should be
    # equivalent.
    paths = [
      'astroid/__init__.py',
      'astroid/absimport.py',
      'astroid/all.py',
      'astroid/clientmodule_test.py',
      'astroid/descriptor_crash.py',
      'astroid/email.py',
      'astroid/format.py',
      'astroid/module.py',
      'astroid/module2.py',
      'astroid/noendingnewline.py',
      'astroid/notall.py',
      'astroid/recursion.py',
      'astroid/suppliermodule_test.py',
    ]
    for path in paths:
      source = read_fixture(path)
      root = ast.parse(source)
      atok = asttokens.ASTTokens(source)
      atok.mark_tokens(root)

      self.verify_all_nodes(atok, root)


  def verify_all_nodes(self, atok, root):
    for node in ast.walk(root):
      if not isinstance(node, (ast.stmt, ast.expr)):
        continue
      text = atok.get_text(node)
      rebuilt_node = parse_snippet(text)

      # Now we need to check if the two nodes are equivalent.
      try:
        self.assertEqual(to_source(rebuilt_node), to_source(node))
      except AssertionError as e:
        print("OUTPUT DIFFERS FOR:", text)
        raise

  def test_deep_recursion(self):
    # This testcase has 1050 strings joined with '+', which causes naive recursions to fail with
    # 'maximum recursion depth exceeded' error.
    source = read_fixture('astroid/joined_strings.py')
    root = ast.parse(source)
    atok = asttokens.ASTTokens(source)
    atok.mark_tokens(root)

    # We handle it find, but we can't use astor.to_source on it because astor chokes. So we check
    # differently.
    all_nodes = collect_nodes_preorder(root)
    self.assertEqual(len(all_nodes), 2104)
    self.assertEqual(atok.get_text(all_nodes[-1]),
                     "'F1akOFFiRIgPHTZksKBAgMCLGTdGNIAAQgKfDAcgZbj0odOnUA8GBAA7'")
    self.assertEqual(atok.get_text(all_nodes[-2]),
                     "'Ii0uLDAxLzI0Mh44U0gxMDI5JkM0JjU3NDY6Kjc5Njo7OUE8Ozw+Oz89QTxA'")
    self.assertEqual(atok.get_text(all_nodes[1053]),
                     "'R0lGODlhigJnAef/AAABAAEEAAkCAAMGAg0GBAYJBQoMCBMODQ4QDRITEBkS'")
    self.assertEqual(atok.get_text(all_nodes[1052]),
                     "'R0lGODlhigJnAef/AAABAAEEAAkCAAMGAg0GBAYJBQoMCBMODQ4QDRITEBkS'\r\n" +
                     "     +'CxsSEhkWDhYYFQ0aJhkaGBweGyccGh8hHiIkIiMmGTEiHhQoPSYoJSkqKDcp'")
    assign = next(n for n in all_nodes if isinstance(n, ast.Assign))
    self.assertTrue(atok.get_text(assign).startswith("x = ("))
    self.assertTrue(atok.get_text(assign).endswith(")"))

    binop = next(n for n in all_nodes if isinstance(n, ast.BinOp))
    self.assertTrue(atok.get_text(binop).startswith("'R0l"))
    self.assertTrue(atok.get_text(binop).endswith("AA7'"))

  def test_print_function(self):
    # This testcase imports print as function (using from __future__). Check that we can parse.
    source = read_fixture('astroid/nonregr.py')
    root = ast.parse(source)
    atok = asttokens.ASTTokens(source)
    atok.mark_tokens(root)
    all_nodes = collect_nodes_preorder(root)

    def get_node_text(line, col, type_name):
      token = atok.get_token(line, col)
      for n in all_nodes:
        if n.first_token == token and n.__class__.__name__ == type_name:
          return atok.get_text(n)

    # Line 16 is: [indent 8] print(v.get('yo'))
    self.assertEqual(get_node_text(16, 8, 'Call'), "print(v.get('yo'))")
    self.assertEqual(get_node_text(16, 14, 'Attribute'), 'v.get')
    self.assertEqual(get_node_text(16, 14, 'Call'), "v.get('yo')")

    if six.PY3:
      self.verify_all_nodes(atok, root)

if __name__ == "__main__":
  unittest.main()
