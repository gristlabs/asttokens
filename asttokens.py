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

"""
This module enhances the Python AST tree with token and source code information, sufficent to
detect the source text of each AST node. This is helpful for tools that make source code
transformations.

It works with both the trees produced by the standard `ast` module, and with those produced by the
`astroid` module (as used by pylint).

See README.md for overview and examples.
"""

import ast
import bisect
import collections
import re
import token
import tokenize
from cStringIO import StringIO



_line_start_re = re.compile(r'^', re.M)

class LineNumbers(object):
  """
  Class to convert between character offsets in a text string, and pairs (line, column) of 1-based
  line and 0-based column numbers, as used by tokens and AST nodes.
  """
  def __init__(self, text):
    # A list of character offsets of each line's first character.
    self._line_offsets = [m.start(0) for m in _line_start_re.finditer(text)]
    self._text_len = len(text)

  def line_to_offset(self, line, column):
    """
    Converts 1-based line number and 0-based column to 0-based character offset into text.
    """
    line -= 1
    if line >= len(self._line_offsets):
      return self._text_len
    elif line < 0:
      return 0
    else:
      return min(self._line_offsets[line] + max(0, column), self._text_len)

  def offset_to_line(self, offset):
    """
    Converts 0-based character offset to pair (line, col) of 1-based line and 0-based column
    numbers.
    """
    offset = max(0, min(self._text_len, offset))
    line_index = bisect.bisect_right(self._line_offsets, offset) - 1
    return (line_index + 1, offset - self._line_offsets[line_index])


def token_repr(tok_type, string):
  """Returns a human-friendly representation of a token with the given type and string."""
  return '%s:%r' % (token.tok_name[tok_type], string)


class Token(collections.namedtuple('Token', 'type string start end line index startpos endpos')):
  """
  TokenInfo is an 8-tuple containing the same 5 fields as the tokens produced by the tokenize
  module, and 3 additional ones useful for this module:
    [0] .type     Token type (see token.py)
    [1] .string   Token (a string)
    [2] .start    Starting (row, column) indices of the token (a 2-tuple of ints)
    [3] .end      Ending (row, column) indices of the token (a 2-tuple of ints)
    [4] .line     Original line (string)
    [5] .index    Index of the token in the list of tokens that it belongs to.
    [6] .startpos Starting character offset into the input text.
    [7] .endpos   Ending character offset into the input text.
  """
  def __str__(self):
    return token_repr(self.type, self.string)


class CodeText(object):
  """
  CodeText maintains the text of Python code in several forms: as a string, as line numbers, and
  as tokens, and is used throughout asttokens to access token and position information.
  """
  def __init__(self, source_text):
    self._text = source_text
    self._line_numbers = LineNumbers(source_text)

    # Tokenize the code.
    self._tokens = list(self._generate_tokens(source_text))

    # Extract the start positions of all tokens, so that we can quickly map positions to tokens.
    self._token_offsets = [tok.startpos for tok in self._tokens]

  def _generate_tokens(self, text):
    """
    Generates tokens for the given code.
    """
    # This is technically an undocumented API for Python3, but allows us to use the same API as for
    # Python2. See http://stackoverflow.com/a/4952291/328565.
    for index, tok in enumerate(tokenize.generate_tokens(StringIO(text).readline)):
      tok_type, tok_str, start, end, line = tok
      yield Token(tok_type, tok_str, start, end, line, index,
                  self._line_numbers.line_to_offset(start[0], start[1]),
                  self._line_numbers.line_to_offset(end[0], end[1]))

  @property
  def text(self):
    """The text of the code represented by this object."""
    return self._text

  @property
  def tokens(self):
    """The list of tokens for this piece of code."""
    return self._tokens

  def get_token_from_offset(self, offset):
    """
    Returns the token containing the given character offset (0-based position in source text),
    or the preceeding token if the position is between tokens.
    """
    return self._tokens[bisect.bisect(self._token_offsets, offset) - 1]

  def get_token(self, lineno, col_offset):
    """
    Returns the token cotntaining the given (lineno, col_offset) position, or the preceeding token
    if the position is between tokens.
    """
    return self.get_token_from_offset(self._line_numbers.line_to_offset(lineno, col_offset))

  def next_token(self, tok, include_extra=False):
    """
    Returns the next token after the given one. If include_extra is True, includes non-coding
    tokens from the tokenize module, such as NL and COMMENT.
    """
    i = tok.index + 1
    if not include_extra:
      while self._tokens[i].type >= token.N_TOKENS:
        i += 1
    return self._tokens[i]

  def prev_token(self, tok, include_extra=False):
    """
    Returns the previous token before the given one. If include_extra is True, includes non-coding
    tokens from the tokenize module, such as NL and COMMENT.
    """
    i = tok.index - 1
    if not include_extra:
      while self._tokens[i].type >= token.N_TOKENS:
        i -= 1
    return self._tokens[i]

  def find_token(self, start_token, tok_type, tok_str=None, reverse=False):
    """
    Looks for the first token, starting at start_token, that matches tok_type and, if given, the
    token string. Searches backwards if reverse is True.
    """
    t = start_token
    advance = self.prev_token if reverse else self.next_token
    while not match_token(t, tok_type, tok_str):
      t = advance(t)
    return t

  def token_range(self, first_token, last_token, include_extra=False):
    """Yields all tokens in order from first_token through and including last_token."""
    for i in xrange(first_token.index, last_token.index + 1):
      if include_extra or self._tokens[i].type < token.N_TOKENS:
        yield self._tokens[i]

  def mark_tokens(self, root_node):
    """
    Given the root of the AST tree produced from source_text, visits all nodes marking them with
    token and position information by adding .first_token and .last_token attributes.
    """
    AssignFirstTokens(self).visit_tree(root_node)
    AssignLastTokens(self).visit_tree(root_node)

  def get_text(self, node):
    """
    After mark_tokens() has been called, returns the text corresponding to the given node.
    """
    if not hasattr(node, 'first_token'):
      return None

    if any(match_token(t, token.NEWLINE) for t in self.get_tokens(node)):
      # Multi-line nodes would be invalid unless we keep the indentation of the first node.
      indent_start = self._text.rfind('\n', 0, node.first_token.startpos) + 1
      return self._text[indent_start : node.last_token.endpos]

    text = self._text[node.first_token.startpos : node.last_token.endpos]
    if (isinstance(node, ast.expr) and
          any(match_token(t, tokenize.NL) for t in self.get_tokens(node, include_extra=True))):
      # TODO This feature probably shouldn't be part of get_text() but get_valid_expr().
      # If we don't have logical lines, but do have newlines, then it's important to parenthesize
      # the text or else it's not valid code. Except that maybe it's already parenthesized.
      if not (node.first_token[:2] in _matching_pairs and
          node.last_token[:2] == _matching_pairs[node.first_token[:2]]):
        return '(' + text + ')'

    return text

  def get_tokens(self, node, include_extra=False):
    return self.token_range(node.first_token, node.last_token, include_extra=include_extra)


def match_token(token, tok_type, tok_str=None):
  """Returns true if token is of the given type and, if given, has the given string."""
  return token.type == tok_type and (tok_str is None or token.string == tok_str)


def _expect_token(token, tok_type, tok_str=None):
  """
  Verifies that the given token is of the expected type. If tok_str is given, the token string
  is verified too.
  """
  if not match_token(token, tok_type, tok_str):
    raise ValueError("Expected token %s, got %s on line %s col %s" % (
      token_repr(tok_type, tok_str), str(token),
      token.start[0], token.start[1] + 1))


def iter_children(node):
  """
  Yields all direct children of a node, skipping children that are singleton nodes.
  """
  for child in ast.iter_child_nodes(node):
    # Skip singleton children; they don't reflect particular positions in the code.
    if not isinstance(child, (ast.expr_context, ast.boolop, ast.operator, ast.unaryop, ast.cmpop)):
      yield child


def walk(node, postorder=False):
  """
  Recursively yield all descendant nodes in the tree starting at node (including node itself),
  in pre-order traversal, or post-order when postorder=True is given.
  """
  return _walk(node, postorder, set())

def _walk(node, postorder, _done):
  # One may wonder if using generators recursively is a good idea (in terms of efficiency). But
  # os.walk() does the same, so it's OK.
  assert node not in _done    # protect against infinite loop in case of a bad tree.
  _done.add(node)
  if not postorder:
    yield node
  for child_node in iter_children(node):
    for n in _walk(child_node, postorder, _done):
      yield n
  if postorder:
    yield node


class NodeMethods(object):
  # TODO: document
  def __init__(self):
    self._cache = {}

  def get(self, obj, cls):
    method = self._cache.get(cls)
    if not method:
      name = "visit_" + cls.__name__.lower()
      method = getattr(obj, name, obj.visit_default)
      self._cache[cls] = method
    return method

_PREVISIT = object()

def visit_tree(node, previsit, postvisit):
  """
  Depth-first scan helper. Rather than use implicit recursion via the function call stack, this
  uses an explicit stack to avoid hitting 'maximum recursion depth exceeded' error. It calls
  previsit and postvisit as follows:
    previsit(node, par_value): par_value is as returned from previsit() of the parent. Should
          return (par_value, value).
    postvisit(node, par_value, value): par_value is as returned from previsit() of the parent, and
          value is as returned from previsit() of this node itself.
  For the initial node, par_value is None.
  Either of previsit and postvisit may be None.
  Returns the return value of the postvisit() call on the root node.
  """
  if not previsit:
    previsit = lambda node, pvalue: (None, None)
  if not postvisit:
    postvisit = lambda node, pvalue, value: None

  ret = None
  stack = [(node, None, _PREVISIT)]
  while stack:
    current, par_value, value = stack.pop()
    if value is _PREVISIT:
      pvalue, post_value = previsit(current, par_value)
      stack.append((current, par_value, post_value))
      children = [(n, pvalue, _PREVISIT) for n in iter_children(current)]
      stack.extend(reversed(children))
    else:
      ret = postvisit(current, par_value, value)
  return ret


class AssignFirstTokens(object):
  """
  Helper that visits all nodes in the AST tree and assigns .first_token attribute to each. If
  position information is not available, it uses the first_token of the first child, and if that's
  not available either, then the first_token of the parent.
  """
  def __init__(self, code):
    self._code = code
    self._methods = NodeMethods()

  def visit_tree(self, node):
    visit_tree(node, self._visit_before_children, self._visit_after_children)

  def _visit_before_children(self, node, parent_token):
    col = getattr(node, 'col_offset', None)
    token = self._code.get_token(node.lineno, col) if col is not None else None
    return (token or parent_token, token)

  def _visit_after_children(self, node, parent_token, token):
    first_child = next(iter_children(node), None)
    if not token or (first_child and first_child.first_token.index < token.index):
      token = first_child.first_token if first_child else parent_token
    node.first_token = self._methods.get(self, node.__class__)(node, token)



  #def visit(self, node, parent_token):
  #  col = getattr(node, 'col_offset', None)
  #  token = self._code.get_token(node.lineno, col) if col is not None else None

  #  first_child = None
  #  for child in iter_children(node):
  #    self.visit(child, token or parent_token)
  #    if not first_child:
  #      first_child = child

  #  if not token or (first_child and first_child.first_token.index < token.index):
  #    token = first_child.first_token if first_child else parent_token

  #  node.first_token = self._methods.get(self, node.__class__)(node, token)

  def visit_default(self, node, first_token):
    # pylint: disable=no-self-use
    return first_token

  def visit_listcomp(self, node, first_token):
    before = self._code.prev_token(first_token)
    _expect_token(before, token.OP, '[')
    return before

  def visit_comprehension(self, node, first_token):
    return self._code.find_token(first_token, token.NAME, 'for', reverse=True)


_matching_pairs = {
  (token.OP, '('): (token.OP, ')'),
  (token.OP, '['): (token.OP, ']'),
  (token.OP, '{'): (token.OP, '}'),
}

#import inspect

class AssignLastTokens(object):
  """
  Helper that visits all nodes in the AST tree and assigns .last_token to each.
  """
  def __init__(self, code):
    self._code =code
    self._methods = NodeMethods()

  def visit_tree(self, node):
    visit_tree(node, None, self._visit_after_children)

  def _visit_after_children(self, node, par_value, value):
    # Find the last child
    child = None
    for child in iter_children(node):
      pass

    # Process the node generically first.
    first = node.first_token
    last = child.last_token if child else first

    # We look for opening parens/braces among non-child nodes. If we find any closing ones, we
    # match them to the opens.
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
      _expect_token(last, *tokens_to_match.pop())

    # Statements continue to before NEWLINE. This helps cover a few different nodes at once.
    if isinstance(node, ast.stmt):
      last = self._find_last_in_line(last)

    node.last_token = self._methods.get(self, node.__class__)(node, child, last)

    #before = self._code.text[node.first_token.startpos - 5 : node.first_token.startpos]
    #middle = self._code.text[node.first_token.startpos : node.last_token.endpos][:10]
    #after = self._code.text[node.last_token.endpos : node.last_token.endpos + 5]
    #print "visited %r %s %s:%s set text '%s<<<%s...>>>%s'" % (
    #  node, inspect.getmro(node.__class__),
    #  getattr(node, 'lineno', None),
    #  getattr(node, 'col_offset', None),
    #  before, middle, after)

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
    for n in iter_children(node):
      for t in self._code.token_range(tok, self._code.prev_token(n.first_token)):
        yield t
      tok = self._code.next_token(n.last_token)

    for t in self._code.token_range(tok, last_token):
      yield t

  def visit_default(self, node, last_child, last):
    # pylint: disable=no-self-use
    return last

  #def visit_classdef(self, node, last_child):
  #  first, last = self.visit_default(node)
  #  if node.doc and not node.body:
  #    last = self._find_token(last, token.STRING)
  #  return (first, last)

  #def visit_functiondef(self, node):
  #  first, last = self.visit_default(node)
  #  if node.doc and not node.body:
  #    last = self._find_token(last, token.STRING)
  #  return (first, last)

  def handle_attr(self, node, last_child, last):
    dot = self._code.next_token(last)
    name = self._code.next_token(dot)
    _expect_token(dot, token.OP, '.')
    _expect_token(name, token.NAME)
    return name

  def visit_attribute(self, node, last_child, last):
    return self.handle_attr(node, last_child, last)

  def visit_assignattr(self, node, last_child, last):
    return self.handle_attr(node, last_child, last)

  def visit_delattr(self, node, last_child, last):
    return self.handle_attr(node, last_child, last)

  def visit_call(self, node, last_child, last):
    return self._code.find_token(last, token.OP, ')')

  def visit_tuple(self, node, last_child, last):
    try:
      maybe_comma = self._code.next_token(last)
      if match_token(maybe_comma, token.OP, ','):
        last = maybe_comma
    except IndexError:
      pass
    return last

  def visit_subscript(self, node, last_child, last):
    return self._code.find_token(last, token.OP, ']')

  ##def visit_index(self, node):
  ##  return self.visit_default(node.value)

  #def visit_listcomp(self, node):
  #  first, last = self.visit_default(node)
  #  before = self.prev_token(first)
  #  after = self.next_token(last)
  #  _expect_token(before, token.OP, '[')
  #  _expect_token(after, token.OP, ']')
  #  return (before, after)

  def visit_num(self, node, last_child, last):
    # A constant like '-1' gets turned into two tokens; this will skip the '-'.
    while match_token(last, token.OP):
      last = self._code.next_token(last)
    return last

