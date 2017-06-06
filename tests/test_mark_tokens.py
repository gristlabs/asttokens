# -*- coding: UTF-8 -*-
from __future__ import unicode_literals, print_function
import astroid
import six
import sys
import textwrap
import unittest
from . import tools


class TestMarkTokens(unittest.TestCase):

  # We use the same test cases to test both nodes produced by the built-in `ast` module, and by
  # the `astroid` library. The latter derives TestAstroid class from TestMarkTokens. For checks
  # that differ between them, .is_astroid_test allows to distinguish.
  is_astroid_test = False

  @classmethod
  def create_mark_checker(cls, source):
    return tools.MarkChecker(source, parse=True)


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
      'a,      # line2\nb +     # line3\n  c +   # line4\n  d',
    })


  def verify_fixture_file(self, path):
    source = tools.read_fixture(path)
    m = self.create_mark_checker(source)
    tested_nodes = m.verify_all_nodes(self)

    exp_index = (0 if six.PY2 else 1) + (2 if self.is_astroid_test else 0)
    exp_tested_nodes = self.expect_tested_nodes[path][exp_index]
    self.assertEqual(tested_nodes, exp_tested_nodes)


  # There is not too much need to verify these counts. The main reason is: if we find that some
  # change reduces the count by a lot, it's a red flag that the test is now covering fewer nodes.
  expect_tested_nodes = {
    #                                   AST       | Astroid
    #                                   Py2   Py3 | Py2   Py3
    'astroid/__init__.py':            ( 4,    4,    4,    4,   ),
    'astroid/absimport.py':           ( 4,    3,    4,    3,   ),
    'astroid/all.py':                 ( 21,   23,   21,   23,  ),
    'astroid/clientmodule_test.py':   ( 75,   67,   69,   69,  ),
    'astroid/descriptor_crash.py':    ( 30,   28,   30,   30,  ),
    'astroid/email.py':               ( 3,    3,    1,    1,   ),
    'astroid/format.py':              ( 64,   61,   62,   62,  ),
    'astroid/module.py':              ( 185,  174,  171,  171, ),
    'astroid/module2.py':             ( 248,  253,  235,  248, ),
    'astroid/noendingnewline.py':     ( 57,   59,   57,   63,  ),
    'astroid/notall.py':              ( 15,   17,   15,   17,  ),
    'astroid/recursion.py':           ( 6,    6,    4,    4,   ),
    'astroid/suppliermodule_test.py': ( 20,   17,   18,   18,  ),
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

    astroid.MANAGER.optimize_ast = True
    try:
      m = self.create_mark_checker(source)
    finally:
      astroid.MANAGER.optimize_ast = False

    if self.is_astroid_test:
      self.assertEqual(len(m.all_nodes), 4)     # This is the result of astroid's optimization
      self.assertEqual(m.view_node_types_at(1, 0), {'Module', 'Assign', 'AssignName'})
      const = next(n for n in m.all_nodes if isinstance(n, astroid.nodes.Const))
      # TODO: Astroid's optimization makes it impossible to get the right start-end information
      # for the combined node. So this test fails. To avoid it, don't set 'optimize_ast=True'. To
      # fix it, astroid would probably need to record the info from the nodes it's combining. Or
      # astroid could avoid the need for the optimization by using an explicit stack like we do.
      #self.assertEqual(m.atok.get_text_range(const), (5, len(source) - 1))
    else:
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

      binop = next(n for n in m.all_nodes if n.__class__.__name__ == 'BinOp')
      self.assertTrue(m.atok.get_text(binop).startswith("'R0l"))
      self.assertTrue(m.atok.get_text(binop).endswith("AA7'"))

    assign = next(n for n in m.all_nodes if n.__class__.__name__ == 'Assign')
    self.assertTrue(m.atok.get_text(assign).startswith("x = ("))
    self.assertTrue(m.atok.get_text(assign).endswith(")"))

  def test_slices(self):
    # Make sure we don't fail on parsing slices of the form `foo[4:]`.
    source = "(foo.Area_Code, str(foo.Phone)[:3], str(foo.Phone)[3:], foo[:], bar[::, :])"
    m = self.create_mark_checker(source)
    self.assertEqual(m.view_nodes_at(1, 1),
                     { "Attribute:foo.Area_Code", "Name:foo", "Tuple:"+source[1:-1] })
    self.assertEqual(m.view_nodes_at(1, 16),
                     { "Subscript:str(foo.Phone)[:3]", "Call:str(foo.Phone)", "Name:str"})
    self.assertEqual(m.view_nodes_at(1, 36),
                     { "Subscript:str(foo.Phone)[3:]", "Call:str(foo.Phone)", "Name:str"})
    # Slice and ExtSlice nodes are wrong, and in particular placed with parents. They are not very
    # important, so we skip them here.
    self.assertEqual({n for n in m.view_nodes_at(1, 56) if 'Slice:' not in n},
                     { "Subscript:foo[:]", "Name:foo" })
    self.assertEqual({n for n in m.view_nodes_at(1, 64) if 'Slice:' not in n},
                     { "Subscript:bar[::, :]", "Name:bar" })

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
    node_name = 'Const' if self.is_astroid_test else 'Str'
    self.assertEqual(m.view_nodes_at(2, 6), {
      node_name + ":'x y z' \\\n'''a b c''' \"u v w\""
    })
    self.assertEqual(m.view_nodes_at(4, 7), {
      node_name + ":'x y z'   # comment2\n       'a b c'   # comment3\n       'u v w'"
    })


  def test_print_function(self):
    # This testcase imports print as function (using from __future__). Check that we can parse it.
    source = tools.read_fixture('astroid/nonregr.py')
    m = self.create_mark_checker(source)

    # Line 16 is: [indent 8] print(v.get('yo'))
    self.assertEqual(m.view_nodes_at(16, 8),
                     { "Call:print(v.get('yo'))", "Expr:print(v.get('yo'))", "Name:print" })
    self.assertEqual(m.view_nodes_at(16, 14), {"Call:v.get('yo')", "Attribute:v.get", "Name:v"})

    if not six.PY2:
      # This verification fails on Py2 because to_string() doesn't know to put parens around the
      # print function. So on Py2 we just rely on the checks above to know that it works.
      m.verify_all_nodes(self)


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
        m.verify_all_nodes(self)
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
        m = self.create_mark_checker(source)
        m.verify_all_nodes(self)


  def test_splat(self):
    # See https://bitbucket.org/plas/thonny/issues/151/debugger-crashes-when-encountering-a-splat
    source = textwrap.dedent("""
      arr = [1,2,3,4,5]
      def print_all(a, b, c, d, e):
          print(a, b, c, d ,e)
      print_all(*arr)
    """)
    m = self.create_mark_checker(source)
    m.verify_all_nodes(self)
    self.assertEqual(m.view_nodes_at(5, 0),
        { "Expr:print_all(*arr)", "Call:print_all(*arr)", "Name:print_all" })
    if not six.PY2 or self.is_astroid_test:
      self.assertEqual(m.view_nodes_at(5, 10), { "Starred:*arr" })
    self.assertEqual(m.view_nodes_at(5, 11), { "Name:arr" })


  def test_paren_attr(self):
    # See https://bitbucket.org/plas/thonny/issues/123/attribute-access-on-parenthesized
    source = "(x).foo()"
    m = self.create_mark_checker(source)
    m.verify_all_nodes(self)
    self.assertEqual(m.view_nodes_at(1, 1), {"Name:x"})
    self.assertEqual(m.view_nodes_at(1, 0),
                     {"Module:(x).foo()", "Expr:(x).foo()", "Call:(x).foo()", "Attribute:(x).foo"})

  def test_conditional_expr(self):
    # See https://bitbucket.org/plas/thonny/issues/108/ast-marker-crashes-with-conditional
    source = "a = True if True else False\nprint(a)"
    m = self.create_mark_checker(source)
    m.verify_all_nodes(self)
    name_a = 'AssignName:a' if self.is_astroid_test else 'Name:a'
    const_true = ('Const:True' if self.is_astroid_test else
                  'Name:True' if six.PY2 else
                  'NameConstant:True')
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
    m.verify_all_nodes(self)
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
      m = self.create_mark_checker(source)
      m.verify_all_nodes(self)

  def test_trailing_commas(self):
    # Make sure we handle trailing commas on comma-separated structures (e.g. tuples, sets, etc.)
    for source in (
      "(a,b,)",
      "[c,d,]",
      "{e,f,}",
      "{h:1,i:2,}"):
      m = self.create_mark_checker(source)
      m.verify_all_nodes(self)

  def test_del_dict(self):
    # See https://bitbucket.org/plas/thonny/issues/24/try-del-from-dictionary-in-debugging-mode
    source = "x = {4:5}\ndel x[4]"
    m = self.create_mark_checker(source)
    m.verify_all_nodes(self)
    self.assertEqual(m.view_nodes_at(1, 4), {'Dict:{4:5}'})
    if self.is_astroid_test:
      self.assertEqual(m.view_nodes_at(1, 5), {'Const:4'})
    else:
      self.assertEqual(m.view_nodes_at(1, 5), {'Num:4'})
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
      m.verify_all_nodes(self)
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
    m.verify_all_nodes(self)
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
      self.assertEqual(m.view_nodes_at(1, 4), {'Num:1'})
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
    """)
    m = self.create_mark_checker(source)
    m.verify_all_nodes(self)
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
