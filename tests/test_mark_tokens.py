# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function

import ast
import inspect
import io
import os
import re
import sys
import textwrap
import token
import unittest
from time import time

import astroid
import six
from asttokens import util, ASTTokens

from . import tools


class TestMarkTokens(unittest.TestCase):
  maxDiff = None

  # We use the same test cases to test both nodes produced by the built-in `ast` module, and by
  # the `astroid` library. The latter derives TestAstroid class from TestMarkTokens. For checks
  # that differ between them, .is_astroid_test allows to distinguish.
  is_astroid_test = False
  module = ast

  def create_mark_checker(self, source, verify=True):
    atok = self.create_asttokens(source)
    checker = tools.MarkChecker(atok)

    # The last token should always be an ENDMARKER
    # None of the nodes should contain that token
    assert atok.tokens[-1].type == token.ENDMARKER
    if atok.text:  # except for empty files
      for node in checker.all_nodes:
        assert node.last_token.type != token.ENDMARKER

    if verify:
      checker.verify_all_nodes(self)
    return checker

  @staticmethod
  def create_asttokens(source):
    return ASTTokens(source, parse=True)

  def print_timing(self):
    # Print the timing of mark_tokens(). This doesn't normally run as a unittest, but if you'd like
    # to see timings, e.g. while optimizing the implementation, run this to see them:
    #
    #     nosetests -m print_timing -s tests.test_mark_tokens tests.test_astroid
    #
    # pylint: disable=no-self-use
    import timeit
    print("mark_tokens", sorted(timeit.repeat(
      setup=textwrap.dedent(
        '''
        import ast, asttokens
        source = "foo(bar(1 + 2), 'hello' + ', ' + 'world')"
        atok = asttokens.ASTTokens(source)
        tree = ast.parse(source)
        '''),
      stmt='atok.mark_tokens(tree)',
      repeat=3,
      number=1000)))


  def test_mark_tokens_simple(self):
    source = tools.read_fixture('astroid', 'module.py')
    m = self.create_mark_checker(source)

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
    if self.is_astroid_test:
      self.assertEqual(m.view_nodes_at(53, 23), {'Comprehension:for (a, b) in MY_DICT if b'})
    else:
      self.assertEqual(m.view_nodes_at(53, 23), {'comprehension:for (a, b) in MY_DICT if b'})

    # Line 59 is: [indent 12] global_access(local, val=autre)
    self.assertEqual(m.view_node_types_at(59, 12), {'Name', 'Call', 'Expr'})
    self.assertEqual(m.view_nodes_at(59, 26), {'Name:local'})
    if self.is_astroid_test:
      self.assertEqual(m.view_nodes_at(59, 33), {'Keyword:val=autre'})
    else:
      self.assertEqual(m.view_nodes_at(59, 33), {'keyword:val=autre'})
    self.assertEqual(m.view_nodes_at(59, 37), {'Name:autre'})

  def test_mark_tokens_multiline(self):
    source = (
"""(    # line1
a,      # line2
b +     # line3
  c +   # line4
  d     # line5
)""")
    m = self.create_mark_checker(source)

    self.assertIn('Name:a', m.view_nodes_at(2, 0))
    self.assertEqual(m.view_nodes_at(3, 0),  {
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
    })
    self.assertIn('Tuple:' + source, m.view_nodes_at(1, 0))


  def verify_fixture_file(self, path):
    source = tools.read_fixture(path)
    m = self.create_mark_checker(source, verify=False)
    tested_nodes = m.verify_all_nodes(self)

    exp_index = (0 if six.PY2 else 1) + (3 if self.is_astroid_test else 0)
    # For ast on Python 3.9, slices are expressions, we handle them and test them.
    if not self.is_astroid_test and issubclass(ast.Slice, ast.expr):
      exp_index += 1
    exp_tested_nodes = self.expect_tested_nodes[path][exp_index]
    self.assertEqual(tested_nodes, exp_tested_nodes)


  # There is not too much need to verify these counts. The main reason is: if we find that some
  # change reduces the count by a lot, it's a red flag that the test is now covering fewer nodes.
  expect_tested_nodes = {
    #                                   AST                  | Astroid
    #                                   Py2   Py3  Py3+slice | Py2   Py3
    'astroid/__init__.py':            ( 4,    4,   4,          4,    4,   ),
    'astroid/absimport.py':           ( 4,    3,   3,          4,    3,   ),
    'astroid/all.py':                 ( 21,   23,  23,         21,   23,  ),
    'astroid/clientmodule_test.py':   ( 75,   67,  67,         69,   69,  ),
    'astroid/descriptor_crash.py':    ( 30,   28,  28,         30,   30,  ),
    'astroid/email.py':               ( 3,    3,   3,          1,    1,   ),
    'astroid/format.py':              ( 64,   61,  61,         62,   62,  ),
    'astroid/module.py':              ( 185,  174, 174,        171,  171, ),
    'astroid/module2.py':             ( 248,  253, 255,        240,  253, ),
    'astroid/noendingnewline.py':     ( 57,   59,  59,         57,   63,  ),
    'astroid/notall.py':              ( 15,   17,  17,         15,   17,  ),
    'astroid/recursion.py':           ( 6,    6,   6,          4,    4,   ),
    'astroid/suppliermodule_test.py': ( 20,   17,  17,         18,   18,  ),
  }

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

    if self.is_astroid_test:
      if getattr(astroid, '__version__', '1') >= '2':
        # Astroid 2 no longer supports this; see
        # https://github.com/PyCQA/astroid/issues/557#issuecomment-396004274
        self.skipTest('astroid-2.0 does not support this')

      # Astroid < 2 does support this with optimize_ast set to True
      astroid.MANAGER.optimize_ast = True
      try:
        m = self.create_mark_checker(source, verify=False)
      finally:
        astroid.MANAGER.optimize_ast = False

      self.assertEqual(len(m.all_nodes), 4)     # This is the result of astroid's optimization
      self.assertEqual(m.view_node_types_at(1, 0), {'Module', 'Assign', 'AssignName'})
      const = next(n for n in m.all_nodes if isinstance(n, astroid.nodes.Const))
      # TODO: Astroid's optimization makes it impossible to get the right start-end information
      # for the combined node. So this test fails. To avoid it, don't set 'optimize_ast=True'. To
      # fix it, astroid would probably need to record the info from the nodes it's combining. Or
      # astroid could avoid the need for the optimization by using an explicit stack like we do.
      #self.assertEqual(m.atok.get_text_range(const), (5, len(source) - 1))
    else:
      m = self.create_mark_checker(source, verify=False)
      self.assertEqual(len(m.all_nodes), 2104)
      self.assertEqual(m.view_node(m.all_nodes[-1]),
                       "Constant:'F1akOFFiRIgPHTZksKBAgMCLGTdGNIAAQgKfDAcgZbj0odOnUA8GBAA7'")
      self.assertEqual(m.view_node(m.all_nodes[-2]),
                       "Constant:'Ii0uLDAxLzI0Mh44U0gxMDI5JkM0JjU3NDY6Kjc5Njo7OUE8Ozw+Oz89QTxA'")
      self.assertEqual(m.view_node(m.all_nodes[1053]),
                       "Constant:'R0lGODlhigJnAef/AAABAAEEAAkCAAMGAg0GBAYJBQoMCBMODQ4QDRITEBkS'")
      self.assertEqual(m.view_node(m.all_nodes[1052]),
                       "BinOp:'R0lGODlhigJnAef/AAABAAEEAAkCAAMGAg0GBAYJBQoMCBMODQ4QDRITEBkS'\r\n" +
                       "     +'CxsSEhkWDhYYFQ0aJhkaGBweGyccGh8hHiIkIiMmGTEiHhQoPSYoJSkqKDcp'")

      binop = next(n for n in m.all_nodes if n.__class__.__name__ == 'BinOp')
      self.assertTrue(m.atok.get_text(binop).startswith("'R0l"))
      self.assertTrue(m.atok.get_text(binop).endswith("AA7'"))

    assign = next(n for n in m.all_nodes if n.__class__.__name__ == 'Assign')
    self.assertTrue(m.atok.get_text(assign).startswith("x = ("))
    self.assertTrue(m.atok.get_text(assign).endswith(")"))

  def test_slices(self):
    # Make sure we don't fail on parsing slices of the form `foo[4:]`.
    source = "(foo.Area_Code, str(foo.Phone)[:3], str(foo.Phone)[3:], foo[:], bar[::2, :], [a[:]][::-1])"
    m = self.create_mark_checker(source)
    self.assertIn("Tuple:" + source, m.view_nodes_at(1, 0))
    self.assertEqual(m.view_nodes_at(1, 1),
                     { "Attribute:foo.Area_Code", "Name:foo" })
    self.assertEqual(m.view_nodes_at(1, 16),
                     { "Subscript:str(foo.Phone)[:3]", "Call:str(foo.Phone)", "Name:str"})
    self.assertEqual(m.view_nodes_at(1, 36),
                     { "Subscript:str(foo.Phone)[3:]", "Call:str(foo.Phone)", "Name:str"})
    # Slice and ExtSlice nodes are wrong, and in particular placed with parents. They are not very
    # important, so we skip them here.
    self.assertEqual({n for n in m.view_nodes_at(1, 56) if 'Slice:' not in n},
                     { "Subscript:foo[:]", "Name:foo" })
    self.assertEqual({n for n in m.view_nodes_at(1, 64) if 'Slice:' not in n},
                     { "Subscript:bar[::2, :]", "Name:bar" })

  def test_adjacent_strings(self):
    source = """
foo = 'x y z' \\
'''a b c''' "u v w"
bar = ('x y z'   # comment2
       'a b c'   # comment3
       'u v w'
      )
"""
    m = self.create_mark_checker(source)
    node_name = 'Const' if self.is_astroid_test else 'Constant'
    self.assertEqual(m.view_nodes_at(2, 6), {
      node_name + ":'x y z' \\\n'''a b c''' \"u v w\""
    })
    self.assertEqual(m.view_nodes_at(4, 7), {
      node_name + ":'x y z'   # comment2\n       'a b c'   # comment3\n       'u v w'"
    })


  def test_print_function(self):
    # This testcase imports print as function (using from __future__). Check that we can parse it.
    # verify_all_nodes doesn't work on Python 2 because the print() call parsed in isolation
    # is viewed as a Print node since it doesn't see the future import
    source = tools.read_fixture('astroid/nonregr.py')
    m = self.create_mark_checker(source, verify=six.PY3)

    # Line 16 is: [indent 8] print(v.get('yo'))
    self.assertEqual(m.view_nodes_at(16, 8),
                     { "Call:print(v.get('yo'))", "Expr:print(v.get('yo'))", "Name:print" })
    self.assertEqual(m.view_nodes_at(16, 14), {"Call:v.get('yo')", "Attribute:v.get", "Name:v"})

  # To make sure we can handle various hard cases, we include tests for issues reported for a
  # similar project here: https://bitbucket.org/plas/thonny

  if not six.PY2:
    def test_nonascii(self):
      # Test of https://bitbucket.org/plas/thonny/issues/162/weird-range-marker-crash-with-non-ascii
      # Only on PY3 because Py2 doesn't support unicode identifiers.
      for source in (
        "sünnikuupäev=str((18+int(isikukood[0:1])-1)//2)+isikukood[1:3]",
        "sünnikuupaev=str((18+int(isikukood[0:1])-1)//2)+isikukood[1:3]"):
        m = self.create_mark_checker(source)
        self.assertEqual(m.view_nodes_at(1, 0), {
          "Module:%s" % source,
          "Assign:%s" % source,
          "%s:%s" % ("AssignName" if self.is_astroid_test else "Name", source[:12])
        })


  if sys.version_info[0:2] >= (3, 6):
    # f-strings are only supported in Python36. We don't handle them fully, for a couple of
    # reasons: parsed AST nodes are not annotated with correct line and col_offset (see
    # https://bugs.python.org/issue29051), and there are confusingly two levels of tokenizing.
    # Meanwhile, we only parse to the level of JoinedStr, and verify that.
    def test_fstrings(self):
      for source in (
        '(f"He said his name is {name!r}.",)',
        "f'{function(kwarg=24)}'",
        'a = f"""result: {value:{width}.{precision}}"""',
        """[f"abc {a['x']} def"]""",
        "def t():\n  return f'{function(kwarg=24)}'"):
        self.create_mark_checker(source)

    def test_adjacent_joined_strings(self):
        source = """
foo = f'x y z' \\
f'''a b c''' f"u v w"
bar = ('x y z'   # comment2
       'a b c'   # comment3
       f'u v w'
      )
"""
        m = self.create_mark_checker(source)
        self.assertEqual(m.view_nodes_at(2, 6), {
            "JoinedStr:f'x y z' \\\nf'''a b c''' f\"u v w\""
        })
        self.assertEqual(m.view_nodes_at(4, 7), {
            "JoinedStr:'x y z'   # comment2\n       'a b c'   # comment3\n       f'u v w'"
        })


  def test_splat(self):
    # See https://bitbucket.org/plas/thonny/issues/151/debugger-crashes-when-encountering-a-splat
    source = textwrap.dedent("""
      arr = [1,2,3,4,5]
      def print_all(a, b, c, d, e):
          print(a, b, c, d ,e)
      print_all(*arr)
    """)
    m = self.create_mark_checker(source)
    self.assertEqual(m.view_nodes_at(5, 0),
        { "Expr:print_all(*arr)", "Call:print_all(*arr)", "Name:print_all" })
    if not six.PY2 or self.is_astroid_test:
      self.assertEqual(m.view_nodes_at(5, 10), { "Starred:*arr" })
    self.assertEqual(m.view_nodes_at(5, 11), { "Name:arr" })


  def test_paren_attr(self):
    # See https://bitbucket.org/plas/thonny/issues/123/attribute-access-on-parenthesized
    source = "(x).foo()"
    m = self.create_mark_checker(source)
    self.assertEqual(m.view_nodes_at(1, 1), {"Name:x"})
    self.assertEqual(m.view_nodes_at(1, 0),
                     {"Module:(x).foo()", "Expr:(x).foo()", "Call:(x).foo()", "Attribute:(x).foo"})

  def test_conditional_expr(self):
    # See https://bitbucket.org/plas/thonny/issues/108/ast-marker-crashes-with-conditional
    source = "a = True if True else False\nprint(a)"
    m = self.create_mark_checker(source)
    name_a = 'AssignName:a' if self.is_astroid_test else 'Name:a'
    const_true = ('Const:True' if self.is_astroid_test else
                  'Name:True' if six.PY2 else
                  'Constant:True')
    self.assertEqual(m.view_nodes_at(1, 0),
                     {name_a, "Assign:a = True if True else False", "Module:" + source})
    self.assertEqual(m.view_nodes_at(1, 4),
                     {const_true, 'IfExp:True if True else False'})
    if six.PY2:
      self.assertEqual(m.view_nodes_at(2, 0), {"Print:print(a)"})
    else:
      self.assertEqual(m.view_nodes_at(2, 0), {"Name:print", "Call:print(a)", "Expr:print(a)"})

  def test_calling_lambdas(self):
    # See https://bitbucket.org/plas/thonny/issues/96/calling-lambdas-crash-the-debugger
    source = "y = (lambda x: x + 1)(2)"
    m = self.create_mark_checker(source)
    self.assertEqual(m.view_nodes_at(1, 4), {'Call:(lambda x: x + 1)(2)'})
    self.assertEqual(m.view_nodes_at(1, 15), {'BinOp:x + 1', 'Name:x'})
    if self.is_astroid_test:
      self.assertEqual(m.view_nodes_at(1, 0), {'AssignName:y', 'Assign:'+source, 'Module:'+source})
    else:
      self.assertEqual(m.view_nodes_at(1, 0), {'Name:y', 'Assign:' + source, 'Module:' + source})

  def test_comprehensions(self):
    # See https://bitbucket.org/plas/thonny/issues/8/range-marker-doesnt-work-correctly-with
    for source in (
      "[(key, val) for key, val in ast.iter_fields(node)]",
      "((key, val) for key, val in ast.iter_fields(node))",
      "{(key, val) for key, val in ast.iter_fields(node)}",
      "{key: val for key, val in ast.iter_fields(node)}",
      "[[c for c in key] for key, val in ast.iter_fields(node)]"):
      self.create_mark_checker(source)

  def test_trailing_commas(self):
    # Make sure we handle trailing commas on comma-separated structures (e.g. tuples, sets, etc.)
    for source in (
      "(a,b,)",
      "[c,d,]",
      "{e,f,}",
      "{h:1,i:2,}"):
      self.create_mark_checker(source)

  def test_tuples(self):
    def get_tuples(code):
      m = self.create_mark_checker(code)
      return [m.atok.get_text(n) for n in m.all_nodes if n.__class__.__name__ == "Tuple"]

    self.assertEqual(get_tuples("a,"), ["a,"])
    self.assertEqual(get_tuples("(a,)"), ["(a,)"])
    self.assertEqual(get_tuples("(a),"), ["(a),"])
    self.assertEqual(get_tuples("((a),)"), ["((a),)"])
    self.assertEqual(get_tuples("(a,),"), ["(a,),", "(a,)"])
    self.assertEqual(get_tuples("((a,),)"), ["((a,),)", "(a,)"])
    self.assertEqual(get_tuples("()"), ["()"])
    self.assertEqual(get_tuples("(),"), ["(),", "()"])
    self.assertEqual(get_tuples("((),)"), ["((),)", "()"])
    self.assertEqual(get_tuples("((),(a,))"), ["((),(a,))", "()", "(a,)"])
    self.assertEqual(get_tuples("((),(a,),)"), ["((),(a,),)", "()", "(a,)"])
    self.assertEqual(get_tuples("((),(a,),),"), ["((),(a,),),", "((),(a,),)", "()", "(a,)"])
    self.assertEqual(get_tuples('((foo, bar),)'), ['((foo, bar),)', '(foo, bar)'])
    self.assertEqual(get_tuples('(foo, bar),'), ['(foo, bar),', '(foo, bar)'])
    self.assertEqual(get_tuples('def foo(a=()): ((x, (y,)),) = ((), (a,),),'), [
      '()', '((x, (y,)),)', '(x, (y,))', '(y,)', '((), (a,),),', '((), (a,),)', '()', '(a,)'])
    self.assertEqual(get_tuples('def foo(a=()): ((x, (y,)),) = [(), [a,],],'), [
      '()', '((x, (y,)),)', '(x, (y,))', '(y,)', '[(), [a,],],', '()'])

  def test_dict_order(self):
    # Make sure we iterate over dict keys/values in source order.
    # See https://github.com/gristlabs/asttokens/issues/31
    source = 'f({1: (2), 3: 4}, object())'
    self.create_mark_checker(source)

  def test_del_dict(self):
    # See https://bitbucket.org/plas/thonny/issues/24/try-del-from-dictionary-in-debugging-mode
    source = "x = {4:5}\ndel x[4]"
    m = self.create_mark_checker(source)
    self.assertEqual(m.view_nodes_at(1, 4), {'Dict:{4:5}'})
    if self.is_astroid_test:
      self.assertEqual(m.view_nodes_at(1, 5), {'Const:4'})
    else:
      self.assertEqual(m.view_nodes_at(1, 5), {'Constant:4'})
    self.assertEqual(m.view_nodes_at(2, 0), {'Delete:del x[4]'})
    self.assertEqual(m.view_nodes_at(2, 4), {'Name:x', 'Subscript:x[4]'})

  if not six.PY2:
    def test_return_annotation(self):
      # See https://bitbucket.org/plas/thonny/issues/9/range-marker-crashes-on-function-return
      source = textwrap.dedent("""
        def liida_arvud(x: int, y: int) -> int:
          return x + y
      """)
      m = self.create_mark_checker(source)
      self.assertEqual(m.view_nodes_at(2, 0),
        {'FunctionDef:def liida_arvud(x: int, y: int) -> int:\n  return x + y'})
      if self.is_astroid_test:
        self.assertEqual(m.view_nodes_at(2, 16),   {'Arguments:x: int, y: int', 'AssignName:x'})
      else:
        self.assertEqual(m.view_nodes_at(2, 16),   {'arguments:x: int, y: int', 'arg:x: int'})
      self.assertEqual(m.view_nodes_at(2, 19),   {'Name:int'})
      self.assertEqual(m.view_nodes_at(2, 35),   {'Name:int'})
      self.assertEqual(m.view_nodes_at(3, 2),    {'Return:return x + y'})

  def test_keyword_arg_only(self):
    # See https://bitbucket.org/plas/thonny/issues/52/range-marker-fails-with-ridastrip-split
    source = "f(x=1)\ng(a=(x),b=[y])"
    m = self.create_mark_checker(source)
    self.assertEqual(m.view_nodes_at(1, 0),
                     {'Name:f', 'Call:f(x=1)', 'Expr:f(x=1)', 'Module:' + source})
    self.assertEqual(m.view_nodes_at(2, 0),
                     {'Name:g', 'Call:g(a=(x),b=[y])', 'Expr:g(a=(x),b=[y])'})
    self.assertEqual(m.view_nodes_at(2, 11), {'Name:y'})
    if self.is_astroid_test:
      self.assertEqual(m.view_nodes_at(1, 2), {'Keyword:x=1'})
      self.assertEqual(m.view_nodes_at(1, 4), {'Const:1'})
      self.assertEqual(m.view_nodes_at(2, 2), {'Keyword:a=(x)'})
      self.assertEqual(m.view_nodes_at(2, 8), {'Keyword:b=[y]'})
    else:
      self.assertEqual(m.view_nodes_at(1, 2), {'keyword:x=1'})
      self.assertEqual(m.view_nodes_at(1, 4), {'Constant:1'})
      self.assertEqual(m.view_nodes_at(2, 2), {'keyword:a=(x)'})
      self.assertEqual(m.view_nodes_at(2, 8), {'keyword:b=[y]'})

  def test_decorators(self):
    # See https://bitbucket.org/plas/thonny/issues/49/range-marker-fails-with-decorators
    source = textwrap.dedent("""
      @deco1
      def f():
        pass
      @deco2(a=1)
      def g(x):
        pass

      @deco3()
      def g(x):
        pass
    """)
    m = self.create_mark_checker(source)
    # The `arguments` node has bogus positions here (and whenever there are no arguments). We
    # don't let that break our test because it's unclear if it matters to anything anyway.
    self.assertIn('FunctionDef:@deco1\ndef f():\n  pass', m.view_nodes_at(2, 0))
    self.assertEqual(m.view_nodes_at(2, 1), {'Name:deco1'})
    if self.is_astroid_test:
      self.assertEqual(m.view_nodes_at(5, 0), {
        'FunctionDef:@deco2(a=1)\ndef g(x):\n  pass',
        'Decorators:@deco2(a=1)'
      })
    else:
      self.assertEqual(m.view_nodes_at(5, 0), {'FunctionDef:@deco2(a=1)\ndef g(x):\n  pass'})
    self.assertEqual(m.view_nodes_at(5, 1), {'Name:deco2', 'Call:deco2(a=1)'})

    self.assertEqual(m.view_nodes_at(9, 1), {'Name:deco3', 'Call:deco3()'})

  def test_with(self):
    source = "with foo: pass"
    m = self.create_mark_checker(source)
    self.assertEqual(m.view_node_types_at(1, 0), {"Module", "With"})
    self.assertEqual(m.view_nodes_at(1, 0), {
      "Module:with foo: pass",
      "With:with foo: pass",
    })

    source = textwrap.dedent(
      '''
      def f(x):
        with A() as a:
          log(a)
          with B() as b, C() as c: log(b, c)
        log(x)
      ''')
    # verification fails on Python2 which turns `with X, Y` turns into `with X: with Y`.
    m = self.create_mark_checker(source, verify=six.PY3)
    self.assertEqual(m.view_nodes_at(5, 4), {
      'With:with B() as b, C() as c: log(b, c)'
    })
    self.assertEqual(m.view_nodes_at(3, 2), {
      'With:  with A() as a:\n    log(a)\n    with B() as b, C() as c: log(b, c)'
    })
    with_nodes = [n for n in m.all_nodes if n.__class__.__name__ == 'With']
    self.assertEqual({m.view_node(n) for n in with_nodes}, {
      'With:with B() as b, C() as c: log(b, c)',
      'With:  with A() as a:\n    log(a)\n    with B() as b, C() as c: log(b, c)',
    })

  def test_one_line_if_elif(self):
    source = """
if 1: a
elif 2: b
    """
    self.create_mark_checker(source)


  def test_statements_with_semicolons(self):
    source = """
a; b; c(
  17
); d # comment1; comment2
if 2: a; b; # comment3
    """
    m = self.create_mark_checker(source)
    self.assertEqual(
      [m.atok.get_text(n) for n in m.all_nodes if util.is_stmt(n)],
      ['a', 'b', 'c(\n  17\n)', 'd', 'if 2: a; b', 'a', 'b'])


  def test_complex_numbers(self):
    source = """
1
-1
j  # not a complex number, just a name
1j
-1j
1+2j
3-4j
1j-1j-1j-1j
    """
    self.create_mark_checker(source)

  def test_parens_around_func(self):
    source = textwrap.dedent(
      '''
      foo()
      (foo)()
      (lambda: 0)()
      (lambda: ())()
      (foo)((1))
      (lambda: ())((2))
      x = (obj.attribute.get_callback() or default_callback)()
      ''')
    m = self.create_mark_checker(source)
    self.assertEqual(m.view_nodes_at(2, 0), {"Name:foo", "Expr:foo()", "Call:foo()"})
    self.assertEqual(m.view_nodes_at(3, 1), {"Name:foo"})
    self.assertEqual(m.view_nodes_at(3, 0), {"Expr:(foo)()", "Call:(foo)()"})
    self.assertEqual(m.view_nodes_at(4, 0), {"Expr:(lambda: 0)()", "Call:(lambda: 0)()"})
    self.assertEqual(m.view_nodes_at(5, 0), {"Expr:(lambda: ())()", "Call:(lambda: ())()"})
    self.assertEqual(m.view_nodes_at(6, 0), {"Expr:(foo)((1))", "Call:(foo)((1))"})
    self.assertEqual(m.view_nodes_at(7, 0), {"Expr:(lambda: ())((2))", "Call:(lambda: ())((2))"})
    self.assertEqual(m.view_nodes_at(8, 4),
                     {"Call:(obj.attribute.get_callback() or default_callback)()"})
    self.assertIn('BoolOp:obj.attribute.get_callback() or default_callback', m.view_nodes_at(8, 5))

  def test_complex_slice_and_parens(self):
    source = 'f((x)[:, 0])'
    self.create_mark_checker(source)

  if six.PY3:
    def test_sys_modules(self):
      """
      Verify all nodes on source files obtained from sys.modules.
      This can take a long time as there are many modules,
      so it only tests all modules if the environment variable
      ASTTOKENS_SLOW_TESTS has been set.
      """
      modules = list(sys.modules.values())
      if not os.environ.get('ASTTOKENS_SLOW_TESTS'):
        modules = modules[:20]

      start = time()
      for module in modules:
        # Don't let this test (which runs twice) take longer than 13 minutes
        # to avoid the travis build time limit of 30 minutes
        if time() - start > 13 * 60:
          break

        try:
          filename = inspect.getsourcefile(module)
        except TypeError:
          continue

        if not filename:
          continue

        filename = os.path.abspath(filename)
        print(filename)
        try:
          with io.open(filename) as f:
            source = f.read()
        except OSError:
          continue

        # Astroid fails with a syntax error if a type comment is on its own line
        if self.is_astroid_test and re.search(r'^\s*# type: ', source, re.MULTILINE):
          print('Skipping', filename)
          continue

        self.create_mark_checker(source)

  if six.PY3:
    def test_dict_merge(self):
      self.create_mark_checker("{**{}}")

    def test_async_def(self):
      self.create_mark_checker("""
async def foo():
  pass

@decorator
async def foo():
  pass
""")

    def test_async_for_and_with(self):
      # Can't verify all nodes because in < 3.7
      # async for/with outside of a function is invalid syntax
      m = self.create_mark_checker("""
async def foo():
  async for x in y: pass
  async with x as y: pass
  """, verify=False)
      assert m.view_nodes_at(3, 2) == {"AsyncFor:async for x in y: pass"}
      assert m.view_nodes_at(4, 2) == {"AsyncWith:async with x as y: pass"}

    def test_await(self):
      # Can't verify all nodes because in astroid
      # await outside of an async function is invalid syntax
      m = self.create_mark_checker("""
async def foo():
  await bar
  """, verify=False)
      assert m.view_nodes_at(3, 2) == {"Await:await bar", "Expr:await bar"}

  if sys.version_info >= (3, 8):
    def test_assignment_expressions(self):
      # From https://www.python.org/dev/peps/pep-0572/
      self.create_mark_checker("""
# Handle a matched regex
if (match := pattern.search(data)) is not None:
    # Do something with match
    pass

# A loop that can't be trivially rewritten using 2-arg iter()
while chunk := file.read(8192):
   process(chunk)

# Reuse a value that's expensive to compute
[y := f(x), y**2, y**3]

# Share a subexpression between a comprehension filter clause and its output
filtered_data = [y for x in data if (y := f(x)) is not None]

y0 = (y1 := f(x))  # Valid, though discouraged

foo(x=(y := f(x)))  # Valid, though probably confusing

def foo(answer=(p := 42)):  # Valid, though not great style
    ...

def foo(answer: (p := 42) = 5):  # Valid, but probably never useful
    ...

lambda: (x := 1) # Valid, but unlikely to be useful

(x := lambda: 1) # Valid

lambda line: (m := re.match(pattern, line)) and m.group(1) # Valid

if any((comment := line).startswith('#') for line in lines):
    print("First comment:", comment)

if all((nonblank := line).strip() == '' for line in lines):
    print("All lines are blank")

partial_sums = [total := total + v for v in values]
""")

  def parse_snippet(self, text, node):
    """
    Returns the parsed AST tree for the given text, handling issues with indentation and newlines
    when text is really an extracted part of larger code.
    """
    # If text is indented, it's a statement, and we need to put in a scope for indents to be valid
    # (using textwrap.dedent is insufficient because some lines may not indented, e.g. comments or
    # multiline strings). If text is an expression but has newlines, we parenthesize it to make it
    # parsable.
    # For expressions and statements, we add a dummy statement '_' before it because if it's just a
    # string contained in an astroid.Const or astroid.Expr it will end up in the doc attribute and be
    # a pain to extract for comparison
    # For starred expressions, e.g. `*args`, we wrap it in a function call to make it parsable.
    # For slices, e.g. `x:`, we wrap it in an indexing expression to make it parsable.
    indented = re.match(r'^[ \t]+\S', text)
    if indented:
      return self.module.parse('def dummy():\n' + text).body[0].body[0]
    if util.is_starred(node):
      return self.module.parse('f(' + text + ')').body[0].value.args[0]
    if util.is_slice(node):
      return self.module.parse('a[' + text + ']').body[0].value.slice
    if util.is_expr(node):
      return self.module.parse('_\n(' + text + ')').body[1].value
    if util.is_module(node):
      return self.module.parse(text)
    return self.module.parse('_\n' + text).body[1]

  def test_assert_nodes_equal(self):
    """
    Checks that assert_nodes_equal actually fails when given different nodes
    """

    def check(s1, s2):
      n1 = self.module.parse(s1)
      n2 = self.module.parse(s2)
      with self.assertRaises(AssertionError):
        self.assert_nodes_equal(n1, n2)

    check('a', 'b')
    check('a*b', 'a+b')
    check('a*b', 'b*a')
    check('(a and b) or c', 'a and (b or c)')
    check('a = 1', 'a = 2')
    check('a = 1', 'a += 1')
    check('a *= 1', 'a += 1')
    check('[a for a in []]', '[a for a in ()]')
    check("for x in y: pass", "for x in y: fail")
    check("1", "1.0")
    check("foo(a, b, *d, c=2, **e)",
          "foo(a, b, *d, c=2.0, **e)")
    check("foo(a, b, *d, c=2, **e)",
          "foo(a, b, *d, c=2)")
    check('def foo():\n    """xxx"""\n    None',
          'def foo():\n    """xx"""\n    None')

  nodes_classes = ast.AST
  context_classes = [ast.expr_context]
  iter_fields = staticmethod(ast.iter_fields)

  def assert_nodes_equal(self, t1, t2):
    # Ignore the context of each node which can change when parsing
    # substrings of source code. We just want equal structure and contents.
    for context_classes_group in self.context_classes:
      if isinstance(t1, context_classes_group):
        self.assertIsInstance(t2, context_classes_group)
        break
    else:
      self.assertEqual(type(t1), type(t2))

    if isinstance(t1, (list, tuple)):
      self.assertEqual(len(t1), len(t2))
      for vc1, vc2 in zip(t1, t2):
        self.assert_nodes_equal(vc1, vc2)
    elif isinstance(t1, self.nodes_classes):
      self.assert_nodes_equal(
        list(self.iter_fields(t1)),
        list(self.iter_fields(t2)),
      )
    else:
      # Weird bug in astroid that collapses spaces in docstrings sometimes maybe
      if self.is_astroid_test and isinstance(t1, six.string_types):
        t1 = re.sub(r'^ +$', '', t1, flags=re.MULTILINE)
        t2 = re.sub(r'^ +$', '', t2, flags=re.MULTILINE)

      self.assertEqual(t1, t2)
