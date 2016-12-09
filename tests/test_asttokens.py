# -*- coding: UTF-8 -*-
from __future__ import unicode_literals, print_function
import ast
import astroid
import asttokens
import copy
import re
import six
import textwrap
import token
import unittest
from .test_mark_tokens import read_fixture, collect_nodes_preorder

def parse_expr(text):
  return parse_stmt('(' + text + ')').value

def parse_stmt(text):
  return ast.parse(text, 'exec').body[0]

def parse_indented(text):
  return parse_stmt('def dummy():\n' + text).body[0]

def parse_snippet(text, is_expr=False):
  """
  Returns the parsed AST tree for the given text, handling issues with indentation when text is
  really an extracted part of larger code.
  """
  # If text is indented, it's a statement, and we need to put in a scope for indents to be valid
  # (using textwrap.dedent is insufficient because some lines may not indented, e.g. comments or
  # multiline strings).
  indented = re.match(r'^[ \t]+\S', text)
  if indented:
    return parse_indented(text)
  return parse_expr(text) if is_expr else parse_stmt(text)


def to_source(node):
  """
  Convert a node to source code by converting it to an astroid tree first, and using astroid's
  as_string() method.
  """
  builder = astroid.rebuilder.TreeRebuilder(astroid.manager.AstroidManager())
  if isinstance(node, ast.Module):
    anode = builder.visit_module(node, '', '', '')
  else:
    # Anything besides Module needs to have astroid Module passed in as a parent.
    amodule = astroid.nodes.Module('', None)
    anode = builder.visit(copy.deepcopy(node), amodule)
  return anode.as_string()


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
    self.assertEqual(to_source(root.body[0]), source)

    source = 'def foo():\n    """xxx"""\n    None'
    root = ast.parse(source).body[0]
    self.assertEqual(to_source(root).strip(), source)


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

      self.verify_all_nodes(atok, root, path + ": ")


  def verify_all_nodes(self, atok, root, prefix=''):
    # A generic way to test an atok.get_text() on the ast tree: for each statement and expression
    # in the tree, we extract the text, parse it, and see if it produces an equivalent tree.
    for node in ast.walk(root):
      if not isinstance(node, (ast.stmt, ast.expr)):
        continue
      text = atok.get_text(node)
      rebuilt_node = parse_snippet(text, is_expr=isinstance(node, ast.expr))

      # Now we need to check if the two nodes are equivalent.
      try:
        self.assertEqual(to_source(rebuilt_node), to_source(node))
      except AssertionError as e:
        print("%sOUTPUT DIFFERS FOR: %s" % (prefix, text))
        raise


  def test_deep_recursion(self):
    # This testcase has 1050 strings joined with '+', which causes naive recursions to fail with
    # 'maximum recursion depth exceeded' error.
    source = read_fixture('astroid/joined_strings.py')
    root = ast.parse(source)
    atok = asttokens.ASTTokens(source)
    atok.mark_tokens(root)

    # We handle it find, but we can't use to_source() on it because it chokes on recursion depth.
    # So we check differently.
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


  # To make sure we can handle various hard cases, we include tests for issues reported for a
  # similar project here: https://bitbucket.org/plas/thonny

  if six.PY3:
    def test_nonascii(self):
      # Test of https://bitbucket.org/plas/thonny/issues/162/weird-range-marker-crash-with-non-ascii
      # Only on PY3 because Py2 doesn't support unicode identifiers.
      for source in (
        "sünnikuupäev=str((18+int(isikukood[0:1])-1)//2)+isikukood[1:3]",
        "sünnikuupaev=str((18+int(isikukood[0:1])-1)//2)+isikukood[1:3]"):
        atok = asttokens.ASTTokens(source)
        root = ast.parse(source)
        atok.mark_tokens(root)
        self.verify_all_nodes(atok, root)
        self.assertEqual(atok.get_text(next(n for n in ast.walk(root) if isinstance(n, ast.Name))),
                         source[:12])


  def test_splat(self):
    # See https://bitbucket.org/plas/thonny/issues/151/debugger-crashes-when-encountering-a-splat
    source = textwrap.dedent("""
      arr = [1,2,3,4,5]
      def print_all(a, b, c, d, e):
          print(a, b, c, d ,e)
      print_all(*arr)
    """)
    atok = asttokens.ASTTokens(source)
    root = ast.parse(source)
    atok.mark_tokens(root)
    self.verify_all_nodes(atok, root)

    names = [n for n in ast.walk(root) if isinstance(n, ast.Name)]
    ranges = sorted((atok.get_text_range(n), n) for n in names)
    end = len(source)
    self.assertEqual(ranges[-2][0], (end - 16, end - 7))
    self.assertEqual(ranges[-1][0], (end - 5, end - 2))
    self.assertEqual(atok.get_text(ranges[-2][1]), 'print_all')
    self.assertEqual(atok.get_text(ranges[-1][1]), 'arr')


  def test_paren_attr(self):
    # See https://bitbucket.org/plas/thonny/issues/123/attribute-access-on-parenthesized
    source = "(x).foo()"
    atok, root, nodes = astparse(source)
    self.verify_all_nodes(atok, root)
    names = [n for n in nodes if isinstance(n, ast.Name)]
    self.assertEqual(range_text(atok, names[0]), (1, 2, "x"))
    self.assertEqual(range_text(atok, names[1]), (1, 2, "foo"))


def astparse(source):
  atok = asttokens.ASTTokens(source)
  root = ast.parse(source)
  atok.mark_tokens(root)
  nodes = sorted(ast.walk(root), key=lambda n: n.first_token.index)
  return (atok, root, nodes)


def range_text(atok, n):
  return atok.get_text_range(n) + (atok.get_text(n),)


if __name__ == "__main__":
  unittest.main()
