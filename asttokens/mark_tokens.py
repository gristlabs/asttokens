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
import token
from . import util


# Mapping of matching braces. To find a token here, look up token[:2].
_matching_pairs = {
  (token.OP, '('): (token.OP, ')'),
  (token.OP, '['): (token.OP, ']'),
  (token.OP, '{'): (token.OP, '}'),
}


class AssignFirstTokens(object):
  """
  Helper that visits all nodes in the AST tree and assigns .first_token attribute to each.
  """
  def __init__(self, code):
    self._code = code
    self._methods = util.NodeMethods()

  def visit_tree(self, node):
    util.visit_tree(node, self._visit_before_children, self._visit_after_children)

  def _visit_before_children(self, node, parent_token):
    col = getattr(node, 'col_offset', None)
    token = self._code.get_token_from_utf8(node.lineno, col) if col is not None else None
    # Use our own token, or our parent's if we don't have one, to pass to child calls as
    # parent_token argument. The second value becomes the token argument of _visit_after_children.
    return (token or parent_token, token)

  def _visit_after_children(self, node, parent_token, token):
    first_child = next(util.iter_children(node), None)
    # If we don't have a token, or if a child starts earlier (indicating that our own position
    # isn't really the start of the node), use the child's first token. If that's not available
    # either, use the parent's.
    if not token or (first_child and first_child.first_token.index < token.index):
      token = first_child.first_token if first_child else parent_token

    # Use node-specific methods to adjust before actually setting it.
    node.first_token = self._methods.get(self, node.__class__)(node, token)

  def visit_default(self, node, first_token):
    # pylint: disable=no-self-use
    # By default, we don't need to adjust the token we computed earlier.
    return first_token

  def visit_listcomp(self, node, first_token):
    # For list comprehensions, we only get the token of the first child, so adjust it to include
    # the opening bracket.
    before = self._code.prev_token(first_token)
    util.expect_token(before, token.OP, '[')
    return before

  def visit_comprehension(self, node, first_token):
    # The 'comprehension' node starts with 'for' but we only get first child; we search backwards
    # to find the 'for' keyword.
    return self._code.find_token(first_token, token.NAME, 'for', reverse=True)


class AssignLastTokens(object):
  """
  Helper that visits all nodes in the AST tree and assigns .last_token to each.
  """
  def __init__(self, code):
    self._code =code
    self._methods = util.NodeMethods()

  def visit_tree(self, node):
    util.visit_tree(node, None, self._visit_after_children)

  def _visit_after_children(self, node, par_value, value):
    # Find the last child
    child = None
    for child in util.iter_children(node):
      pass

    # Process the node generically first.
    first = node.first_token
    last = child.last_token if child else first

    # We look for opening parens/braces among non-child tokens (i.e. those between our actual
    # child nodes). If we find any closing ones, we match them to the opens.
    tokens_to_match = []
    for tok in self._iter_non_child_tokens(first, last, node):
      tok_info = tok[:2]
      if tokens_to_match and tok_info == tokens_to_match[-1]:
        tokens_to_match.pop()
      elif tok_info in _matching_pairs:
        tokens_to_match.append(_matching_pairs[tok_info])

    # Once done, extend `last` to match any unclosed parens/braces.
    while tokens_to_match:
      last = self._code.next_token(last)
      util.expect_token(last, *tokens_to_match.pop())

    # Statements continue to before NEWLINE. This helps cover a few different cases at once.
    if isinstance(node, ast.stmt):
      last = self._find_last_in_line(last)

    # Finally, give a chance to node-specific methods to adjust
    node.last_token = self._methods.get(self, node.__class__)(node, child, last)

  def _find_last_in_line(self, start_token):
    try:
      newline = self._code.find_token(start_token, token.NEWLINE)
    except IndexError:
      newline = self._code.find_token(start_token, token.ENDMARKER)
    return self._code.prev_token(newline)

  def _iter_non_child_tokens(self, first_token, last_token, node):
    """
    Generates all tokens in [first_token, last_token] range that do not belong to any children of
    node. E.g. `foo(bar)` has children `foo` and `bar`, but we would yield the `(`.
    """
    tok = first_token
    for n in util.iter_children(node):
      for t in self._code.token_range(tok, self._code.prev_token(n.first_token)):
        yield t
      if n.last_token.index >= last_token.index:
        return
      tok = self._code.next_token(n.last_token)

    for t in self._code.token_range(tok, last_token):
      yield t

  def visit_default(self, node, last_child, last):
    # pylint: disable=no-self-use
    return last

  def handle_attr(self, node, last_child, last):
    # Attribute node has ".attr" (2 tokens) after the last child.
    dot = self._code.next_token(last)
    name = self._code.next_token(dot)
    util.expect_token(dot, token.OP, '.')
    util.expect_token(name, token.NAME)
    return name

  visit_attribute = handle_attr
  visit_assignattr = handle_attr
  visit_delattr = handle_attr

  def visit_call(self, node, last_child, last):
    # A function call isn't over until we see a closing paren. Remember that last is at the end of
    # all children, so we are not worried about encountering a paren that belongs to a child.
    return self._code.find_token(last, token.OP, ')')

  def visit_subscript(self, node, last_child, last):
    # A subscript operations isn't over until we see a closing bracket. Similar to function calls.
    return self._code.find_token(last, token.OP, ']')

  def visit_tuple(self, node, last_child, last):
    # A tuple doesn't include parens; if there is a trailing comma, make it part of the tuple.
    try:
      maybe_comma = self._code.next_token(last)
      if util.match_token(maybe_comma, token.OP, ','):
        last = maybe_comma
    except IndexError:
      pass
    return last

  def visit_num(self, node, last_child, last):
    # A constant like '-1' gets turned into two tokens; this will skip the '-'.
    while util.match_token(last, token.OP):
      last = self._code.next_token(last)
    return last

