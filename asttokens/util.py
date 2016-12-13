# Copyright 2016 Grist Labs, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import ast
import collections
import token
from six import iteritems


def token_repr(tok_type, string):
  """Returns a human-friendly representation of a token with the given type and string."""
  # repr() prefixes unicode with 'u' on Python2 but not Python3; strip it out for consistency.
  return '%s:%s' % (token.tok_name[tok_type], repr(string).lstrip('u'))


class Token(collections.namedtuple('Token', 'type string start end line index startpos endpos')):
  """
  TokenInfo is an 8-tuple containing the same 5 fields as the tokens produced by the tokenize
  module, and 3 additional ones useful for this module:

  - [0] .type     Token type (see token.py)
  - [1] .string   Token (a string)
  - [2] .start    Starting (row, column) indices of the token (a 2-tuple of ints)
  - [3] .end      Ending (row, column) indices of the token (a 2-tuple of ints)
  - [4] .line     Original line (string)
  - [5] .index    Index of the token in the list of tokens that it belongs to.
  - [6] .startpos Starting character offset into the input text.
  - [7] .endpos   Ending character offset into the input text.
  """
  def __str__(self):
    return token_repr(self.type, self.string)


def match_token(token, tok_type, tok_str=None):
  """Returns true if token is of the given type and, if a string is given, has that string."""
  return token.type == tok_type and (tok_str is None or token.string == tok_str)


def expect_token(token, tok_type, tok_str=None):
  """
  Verifies that the given token is of the expected type. If tok_str is given, the token string
  is verified too. If the token doesn't match, raises an informative ValueError.
  """
  if not match_token(token, tok_type, tok_str):
    raise ValueError("Expected token %s, got %s on line %s col %s" % (
      token_repr(tok_type, tok_str), str(token),
      token.start[0], token.start[1] + 1))


def iter_children(node):
  """
  Yields all direct children of a AST node, skipping children that are singleton nodes.
  """
  if hasattr(node, 'get_children'):
    for c in node.get_children():
      yield c
    return

  for child in ast.iter_child_nodes(node):
    # Skip singleton children; they don't reflect particular positions in the code.
    if not isinstance(child, (ast.expr_context, ast.boolop, ast.operator, ast.unaryop, ast.cmpop)):
      yield child


stmt_class_names = {n for n, c in iteritems(ast.__dict__)
                    if isinstance(c, type) and issubclass(c, ast.stmt)}
expr_class_names = ({n for n, c in iteritems(ast.__dict__)
                    if isinstance(c, type) and issubclass(c, ast.expr)} |
                    {'AssignName', 'DelName', 'Const', 'AssignAttr', 'DelAttr'})

# These feel hacky compared to isinstance() but allow us to work with both ast and astroid nodes
# in the same way, and without even importing astroid.
def is_expr(node):
  """Returns whether node is an expression node."""
  return node.__class__.__name__ in expr_class_names

def is_stmt(node):
  """Returns whether node is a statement node."""
  return node.__class__.__name__ in stmt_class_names

def is_module(node):
  """Returns whether node is a module node."""
  return node.__class__.__name__ == 'Module'


# Sentinel value used by visit_tree().
_PREVISIT = object()

def visit_tree(node, previsit, postvisit):
  """
  Scans the tree under the node depth-first using an explicit stack. It avoids implicit recursion
  via the function call stack to avoid hitting 'maximum recursion depth exceeded' error.

  It calls ``previsit()`` and ``postvisit()`` as follows:

  * ``previsit(node, par_value)`` - should return ``(par_value, value)``
        ``par_value`` is as returned from ``previsit()`` of the parent.

  * ``postvisit(node, par_value, value)`` - should return ``value``
        ``par_value`` is as returned from ``previsit()`` of the parent, and ``value`` is as
        returned from ``previsit()`` of this node itself. The return ``value`` is ignored except
        the one for the root node, which is returned from the overall ``visit_tree()`` call.

  For the initial node, ``par_value`` is None. Either ``previsit`` and ``postvisit`` may be None.
  """
  if not previsit:
    previsit = lambda node, pvalue: (None, None)
  if not postvisit:
    postvisit = lambda node, pvalue, value: None

  done = set()
  ret = None
  stack = [(node, None, _PREVISIT)]
  while stack:
    current, par_value, value = stack.pop()
    if value is _PREVISIT:
      assert current not in done    # protect againt infinite loop in case of a bad tree.
      done.add(current)

      pvalue, post_value = previsit(current, par_value)
      stack.append((current, par_value, post_value))
      children = [(n, pvalue, _PREVISIT) for n in iter_children(current)]
      stack.extend(reversed(children))
    else:
      ret = postvisit(current, par_value, value)
  return ret


class NodeMethods(object):
  """
  Helper to get `visit_{node_type}` methods given a node's class and cache the results.
  """
  def __init__(self):
    self._cache = {}

  def get(self, obj, cls):
    """
    Using the lowercase name of the class as node_type, returns `obj.visit_{node_type}`,
    or `obj.visit_default` if the type-specific method is not found.
    """
    method = self._cache.get(cls)
    if not method:
      name = "visit_" + cls.__name__.lower()
      method = getattr(obj, name, obj.visit_default)
      self._cache[cls] = method
    return method
