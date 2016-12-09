# -*- coding: UTF-8 -*-
from __future__ import unicode_literals
import ast
import asttokens
import six
import textwrap
import unittest
from . import tools


class TestMarkTokens(unittest.TestCase):

  def test_mark_tokens_simple(self):
    source = tools.read_fixture('astroid', 'module.py')
    m = tools.MarkChecker(source)

    # Line 14 is: [indent 4] MY_DICT[key] = val
    self.assertEqual(m.view_nodes_at(14, 4), {
      "Name:MY_DICT",
      "Subscript:MY_DICT[key]",
      "Assign:MY_DICT[key] = val"
    })

    # Line 35 is: [indent 12] raise XXXError()
    self.assertEqual(m.view_nodes_at(35, 12), {'Raise:raise XXXError()'})
    self.assertEqual(m.view_nodes_at(35, 18), {'Call:XXXError()', 'Name:XXXError'})

    # Line 53 is: [indent 12] autre = [a for (a, b) in MY_DICT if b]
    self.assertEqual(m.view_nodes_at(53, 20), {'ListComp:[a for (a, b) in MY_DICT if b]'})
    self.assertEqual(m.view_nodes_at(53, 21), {'Name:a'})
    self.assertEqual(m.view_nodes_at(53, 23), {'comprehension:for (a, b) in MY_DICT if b'})

    # Line 59 is: [indent 12] global_access(local, val=autre)
    self.assertEqual(m.view_node_types_at(59, 12), {'Name', 'Call', 'Expr'})
    self.assertEqual(m.view_node_types_at(59, 26), {'Name'})
    self.assertEqual(m.view_node_types_at(59, 37), {'Name', 'keyword'})

  def test_mark_tokens_multiline(self):
    source = (
"""(    # line1
a,      # line2
b +     # line3
  c +   # line4
  d     # line5
)""")
    m = tools.MarkChecker(source)

    self.assertIn('Name:a', m.view_nodes_at(2, 0))
    self.assertEquals(m.view_nodes_at(3, 0),  {
      'Name:b',
      'BinOp:b +     # line3\n  c',
      'BinOp:b +     # line3\n  c +   # line4\n  d',
    })

    all_text = {m.atok.get_text(node) for node in m.all_nodes}
    self.assertEqual(all_text, {
      source,
      'a', 'b', 'c', 'd',
      # All other expressions preserve newlines and comments but are parenthesized.
      'b +     # line3\n  c',
      'b +     # line3\n  c +   # line4\n  d',
      'a,      # line2\nb +     # line3\n  c +   # line4\n  d',
    })


  def verify_fixture_file(self, path):
    source = tools.read_fixture(path)
    m = tools.MarkChecker(source)
    m.verify_all_nodes(self)

  # This set of methods runs verifications for the variety of syntax constructs used in the
  # fixture test files.
  # pylint: disable=multiple-statements
  def test_fixture1(self): self.verify_fixture_file('astroid/__init__.py')
  def test_fixture2(self): self.verify_fixture_file('astroid/absimport.py')
  def test_fixture3(self): self.verify_fixture_file('astroid/all.py')
  def test_fixture4(self): self.verify_fixture_file('astroid/clientmodule_test.py')
  def test_fixture5(self): self.verify_fixture_file('astroid/descriptor_crash.py')
  def test_fixture6(self): self.verify_fixture_file('astroid/email.py')
  def test_fixture7(self): self.verify_fixture_file('astroid/format.py')
  def test_fixture8(self): self.verify_fixture_file('astroid/module.py')
  def test_fixture9(self): self.verify_fixture_file('astroid/module2.py')
  def test_fixture10(self): self.verify_fixture_file('astroid/noendingnewline.py')
  def test_fixture11(self): self.verify_fixture_file('astroid/notall.py')
  def test_fixture12(self): self.verify_fixture_file('astroid/recursion.py')
  def test_fixture13(self): self.verify_fixture_file('astroid/suppliermodule_test.py')

  def test_deep_recursion(self):
    # This testcase has 1050 strings joined with '+', which causes naive recursions to fail with
    # 'maximum recursion depth exceeded' error. We actually handle it just fine, but we can't use
    # to_source() on it because it chokes on recursion depth. So we test individual nodes.
    source = tools.read_fixture('astroid/joined_strings.py')
    m = tools.MarkChecker(source)

    self.assertEqual(len(m.all_nodes), 2104)
    self.assertEqual(m.view_node(m.all_nodes[-1]),
                     "Str:'F1akOFFiRIgPHTZksKBAgMCLGTdGNIAAQgKfDAcgZbj0odOnUA8GBAA7'")
    self.assertEqual(m.view_node(m.all_nodes[-2]),
                     "Str:'Ii0uLDAxLzI0Mh44U0gxMDI5JkM0JjU3NDY6Kjc5Njo7OUE8Ozw+Oz89QTxA'")
    self.assertEqual(m.view_node(m.all_nodes[1053]),
                     "Str:'R0lGODlhigJnAef/AAABAAEEAAkCAAMGAg0GBAYJBQoMCBMODQ4QDRITEBkS'")
    self.assertEqual(m.view_node(m.all_nodes[1052]),
                     "BinOp:'R0lGODlhigJnAef/AAABAAEEAAkCAAMGAg0GBAYJBQoMCBMODQ4QDRITEBkS'\r\n" +
                     "     +'CxsSEhkWDhYYFQ0aJhkaGBweGyccGh8hHiIkIiMmGTEiHhQoPSYoJSkqKDcp'")

    assign = next(n for n in m.all_nodes if isinstance(n, ast.Assign))
    self.assertTrue(m.atok.get_text(assign).startswith("x = ("))
    self.assertTrue(m.atok.get_text(assign).endswith(")"))

    binop = next(n for n in m.all_nodes if isinstance(n, ast.BinOp))
    self.assertTrue(m.atok.get_text(binop).startswith("'R0l"))
    self.assertTrue(m.atok.get_text(binop).endswith("AA7'"))


  def test_print_function(self):
    # This testcase imports print as function (using from __future__). Check that we can parse it.
    source = tools.read_fixture('astroid/nonregr.py')
    m = tools.MarkChecker(source)

    # Line 16 is: [indent 8] print(v.get('yo'))
    self.assertEqual(m.view_nodes_at(16, 8),
                     { "Call:print(v.get('yo'))", "Expr:print(v.get('yo'))", "Name:print" })
    self.assertEqual(m.view_nodes_at(16, 14), {"Call:v.get('yo')", "Attribute:v.get", "Name:v"})

    if six.PY3:
      # This verification fails on Py2 because to_string() doesn't know to put parens around the
      # print function. So on Py2 we just rely on the checks above to know that it works.
      m.verify_all_nodes(self)


  # To make sure we can handle various hard cases, we include tests for issues reported for a
  # similar project here: https://bitbucket.org/plas/thonny

  if six.PY3:
    def test_nonascii(self):
      # Test of https://bitbucket.org/plas/thonny/issues/162/weird-range-marker-crash-with-non-ascii
      # Only on PY3 because Py2 doesn't support unicode identifiers.
      for source in (
        "sünnikuupäev=str((18+int(isikukood[0:1])-1)//2)+isikukood[1:3]",
        "sünnikuupaev=str((18+int(isikukood[0:1])-1)//2)+isikukood[1:3]"):
        m = tools.MarkChecker(source)
        m.verify_all_nodes(self)
        self.assertEqual(m.view_nodes_at(1, 0), {
          "Module:%s" % source,
          "Assign:%s" % source,
          "Name:%s" % source[:12]
        })


  def test_splat(self):
    # See https://bitbucket.org/plas/thonny/issues/151/debugger-crashes-when-encountering-a-splat
    source = textwrap.dedent("""
      arr = [1,2,3,4,5]
      def print_all(a, b, c, d, e):
          print(a, b, c, d ,e)
      print_all(*arr)
    """)
    m = tools.MarkChecker(source)
    m.verify_all_nodes(self)
    self.assertEqual(m.view_nodes_at(5, 0),
        { "Expr:print_all(*arr)", "Call:print_all(*arr)", "Name:print_all" })
    self.assertEqual(m.view_nodes_at(5, 11), { "Name:arr" })


  def test_paren_attr(self):
    # See https://bitbucket.org/plas/thonny/issues/123/attribute-access-on-parenthesized
    source = "(x).foo()"
    m = tools.MarkChecker(source)
    m.verify_all_nodes(self)
    self.assertEqual(m.view_nodes_at(1, 1), {"Name:x"})
    self.assertEqual(m.view_nodes_at(1, 4), {"Name:foo", "Call:foo()"})
    self.assertEqual(m.view_nodes_at(1, 0),
                     {"Module:(x).foo()", "Expr:(x).foo()", "Attribute:(x).foo"})
