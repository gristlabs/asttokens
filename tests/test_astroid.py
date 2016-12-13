# -*- coding: UTF-8 -*-
from __future__ import unicode_literals, print_function
import astroid
from . import tools, test_mark_tokens


class TestAstroid(test_mark_tokens.TestMarkTokens):

  is_astroid_test = True

  @classmethod
  def create_mark_checker(cls, source):
    builder = astroid.builder.AstroidBuilder()
    tree = builder.string_build(source)
    return tools.MarkChecker(source, tree=tree)
