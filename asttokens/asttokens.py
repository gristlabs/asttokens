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
import bisect
import io
import sys
import token
import tokenize
from ast import Module
from typing import Callable, Iterator, List, Optional, Tuple, Any, cast, TYPE_CHECKING, Type

import six
from six.moves import xrange  # pylint: disable=redefined-builtin

from .line_numbers import LineNumbers
from .util import Token, match_token, is_non_coding_token, patched_generate_tokens, last_stmt

if TYPE_CHECKING:
  from .util import AstNode


class ASTTokens(object):
  """
  ASTTokens maintains the text of Python code in several forms: as a string, as line numbers, and
  as tokens, and is used to mark and access token and position information.

  ``source_text`` must be a unicode or UTF8-encoded string. If you pass in UTF8 bytes, remember
  that all offsets you'll get are to the unicode text, which is available as the ``.text``
  property.

  If ``parse`` is set, the ``source_text`` will be parsed with ``ast.parse()``, and the resulting
  tree marked with token info and made available as the ``.tree`` property.

  If ``tree`` is given, it will be marked and made available as the ``.tree`` property. In
  addition to the trees produced by the ``ast`` module, ASTTokens will also mark trees produced
  using ``astroid`` library <https://www.astroid.org>.

  If only ``source_text`` is given, you may use ``.mark_tokens(tree)`` to mark the nodes of an AST
  tree created separately.
  """

  def __init__(self, source_text, parse=False, tree=None, filename='<unknown>', init_tokens=True):
    # type: (Any, bool, Optional[Module], str, bool) -> None
    # FIXME: Strictly, the type of source_type is one of the six string types, but hard to specify with mypy given
    # https://mypy.readthedocs.io/en/stable/common_issues.html#variables-vs-type-aliases

    self._filename = filename
    self._tree = ast.parse(source_text, filename) if parse else tree

    # Decode source after parsing to let Python 2 handle coding declarations.
    # (If the encoding was not utf-8 compatible, then even if it parses correctly,
    # we'll fail with a unicode error here.)
    source_text = six.ensure_text(source_text)

    self._text = source_text
    self._line_numbers = LineNumbers(source_text)

    self._tokens = None  # type: Optional[List[Token]]
    self._token_offsets = None  # type: Optional[List[int]]

    if not init_tokens and not isinstance(self._tree, (ast.AST, type(None))):
      raise ValueError('init_tokens=False is only supported for AST trees')

    if init_tokens or not supports_unmarked(self._tree):
      self.init_tokens()

  def init_tokens(self):
    # type: () -> None
    if self._tokens is not None:
      return

    # Tokenize the code.
    self._tokens = list(self._generate_tokens(self._text))

    # Extract the start positions of all tokens, so that we can quickly map positions to tokens.
    self._token_offsets = [tok.startpos for tok in self._tokens]

    if self._tree:
      self.mark_tokens(self._tree)

  def mark_tokens(self, root_node):
    # type: (Module) -> None
    """
    Given the root of the AST or Astroid tree produced from source_text, visits all nodes marking
    them with token and position information by adding ``.first_token`` and
    ``.last_token``attributes. This is done automatically in the constructor when ``parse`` or
    ``tree`` arguments are set, but may be used manually with a separate AST or Astroid tree.
    """
    # The hard work of this class is done by MarkTokens
    from .mark_tokens import MarkTokens # to avoid import loops
    MarkTokens(self).visit_tree(root_node)

  def _generate_tokens(self, text):
    # type: (str) -> Iterator[Token]
    """
    Generates tokens for the given code.
    """
    # tokenize.generate_tokens is technically an undocumented API for Python3, but allows us to use the same API as for
    # Python2. See http://stackoverflow.com/a/4952291/328565.
    # FIXME: Remove cast once https://github.com/python/typeshed/issues/7003 gets fixed
    original_tokens = tokenize.generate_tokens(cast(Callable[[], str], io.StringIO(text).readline))
    for index, tok in enumerate(patched_generate_tokens(original_tokens)):
      tok_type, tok_str, start, end, line = tok
      yield Token(tok_type, tok_str, start, end, line, index,
                  self._line_numbers.line_to_offset(start[0], start[1]),
                  self._line_numbers.line_to_offset(end[0], end[1]))

  @property
  def text(self):
    # type: () -> str
    """The source code passed into the constructor."""
    return self._text

  @property
  def tokens(self):
    # type: () -> List[Token]
    """The list of tokens corresponding to the source code from the constructor."""
    assert self._tokens
    return self._tokens

  @property
  def tree(self):
    # type: () -> Optional[Module]
    """The root of the AST tree passed into the constructor or parsed from the source code."""
    return self._tree

  @property
  def filename(self):
    # type: () -> str
    """The filename that was parsed"""
    return self._filename

  def get_token_from_offset(self, offset):
    # type: (int) -> Token
    """
    Returns the token containing the given character offset (0-based position in source text),
    or the preceeding token if the position is between tokens.
    """
    assert self._token_offsets and self._tokens
    return self._tokens[bisect.bisect(self._token_offsets, offset) - 1]

  def get_token(self, lineno, col_offset):
    # type: (int, int) -> Token
    """
    Returns the token containing the given (lineno, col_offset) position, or the preceeding token
    if the position is between tokens.
    """
    # TODO: add test for multibyte unicode. We need to translate offsets from ast module (which
    # are in utf8) to offsets into the unicode text. tokenize module seems to use unicode offsets
    # but isn't explicit.
    return self.get_token_from_offset(self._line_numbers.line_to_offset(lineno, col_offset))

  def get_token_from_utf8(self, lineno, col_offset):
    # type: (int, int) -> Token
    """
    Same as get_token(), but interprets col_offset as a UTF8 offset, which is what `ast` uses.
    """
    return self.get_token(lineno, self._line_numbers.from_utf8_col(lineno, col_offset))

  def next_token(self, tok, include_extra=False):
    # type: (Token, bool) -> Token
    """
    Returns the next token after the given one. If include_extra is True, includes non-coding
    tokens from the tokenize module, such as NL and COMMENT.
    """
    i = tok.index + 1
    assert self._tokens
    if not include_extra:
      while is_non_coding_token(self._tokens[i].type):
        i += 1
    return self._tokens[i]

  def prev_token(self, tok, include_extra=False):
    # type: (Token, bool) -> Token
    """
    Returns the previous token before the given one. If include_extra is True, includes non-coding
    tokens from the tokenize module, such as NL and COMMENT.
    """
    i = tok.index - 1
    assert self._tokens
    if not include_extra:
      while is_non_coding_token(self._tokens[i].type):
        i -= 1
    return self._tokens[i]

  def find_token(self, start_token, tok_type, tok_str=None, reverse=False):
    # type: (Token, int, Optional[str], bool) -> Token
    """
    Looks for the first token, starting at start_token, that matches tok_type and, if given, the
    token string. Searches backwards if reverse is True. Returns ENDMARKER token if not found (you
    can check it with `token.ISEOF(t.type)`.
    """
    t = start_token
    advance = self.prev_token if reverse else self.next_token
    while not match_token(t, tok_type, tok_str) and not token.ISEOF(t.type):
      t = advance(t, include_extra=True)
    return t

  def token_range(self,
                  first_token,  # type: Token
                  last_token,  # type: Token
                  include_extra=False,  # type: bool
                  ):
    # type: (...) -> Iterator[Token]
    """
    Yields all tokens in order from first_token through and including last_token. If
    include_extra is True, includes non-coding tokens such as tokenize.NL and .COMMENT.
    """
    assert self._tokens
    for i in xrange(first_token.index, last_token.index + 1):
      if include_extra or not is_non_coding_token(self._tokens[i].type):
        yield self._tokens[i]

  def get_tokens(self, node, include_extra=False):
    # type: (AstNode, bool) -> Iterator[Token]
    """
    Yields all tokens making up the given node. If include_extra is True, includes non-coding
    tokens such as tokenize.NL and .COMMENT.
    """
    return self.token_range(node.first_token, node.last_token, include_extra=include_extra)

  def get_text_range(self, node):
    # type: (AstNode) -> Tuple[int, int]
    """
    After mark_tokens() has been called, returns the (startpos, endpos) positions in source text
    corresponding to the given node. Returns (0, 0) for nodes (like `Load`) that don't correspond
    to any particular text.
    """
    if not self._tokens and supports_unmarked(node):
      return self.get_text_range_unmarked(node)

    self.init_tokens()

    if not hasattr(node, 'first_token'):
      return (0, 0)

    start = node.first_token.startpos
    if any(match_token(t, token.NEWLINE) for t in self.get_tokens(node)):
      # Multi-line nodes would be invalid unless we keep the indentation of the first node.
      start = self._text.rfind('\n', 0, start) + 1

    return (start, node.last_token.endpos)

  def get_text(self, node):
    # type: (AstNode) -> str
    """
    After mark_tokens() has been called, returns the text corresponding to the given node. Returns
    '' for nodes (like `Load`) that don't correspond to any particular text.
    """
    start, end = self.get_text_range(node)
    return self._text[start : end]

  def get_text_range_unmarked(self, node):
    # type: (ast.AST) -> Tuple[int, int]
    """
    Like get_text_range(), but works without requiring mark_tokens() to have been called.
    Requires Python 3.8+. Doesn't support astroid.
    """
    if not supports_unmarked():
      raise NotImplementedError('Python version not supported')

    if not isinstance(node, ast.AST):
      raise NotImplementedError('Not supported for astroid')

    if isinstance(node, ast.Module):
      # Modules don't have position info, so just return the range of the whole text.
      # get_text does something different, but its behavior seems weird and inconsistent.
      # For example, in a file with only comments, it only returns the first line.
      # It's hard to imagine a case when this matters.
      return 0, len(self._text)
    elif not hasattr(node, 'lineno'):
      return 0, 0
    else:
      decorators = getattr(node, 'decorator_list', [])
      if decorators:
        # Function/Class definition nodes are marked by AST as starting at def/class,
        # not the first decorator. This doesn't match the original get_text[_range] behavior,
        # or inspect.getsource(), and just seems weird.
        start_node = decorators[0]
      else:
        start_node = node
      start = self._line_numbers.utf8_to_offset(
        start_node.lineno,
        start_node.col_offset,
      )
      # Like get_text_range(), keep the indentation of the first line
      # of a multi-line, multi-statement node.
      if last_stmt(node).lineno != node.lineno:
        start = self._text.rfind('\n', 0, start) + 1

    # To match the behavior of get_text_range, we exclude trailing semicolons and comments.
    # This means that for blocks containing multiple statements, we have to use the last one
    # instead of the actual node for end_lineno and end_col_offset.
    end_node = last_stmt(node)
    end = self._line_numbers.utf8_to_offset(
      cast(int, end_node.end_lineno),
      cast(int, end_node.end_col_offset),
    )

    return start, end

  def get_text_unmarked(self, node):
    # type: (ast.AST) -> str
    """
    Like get_text(), but works without requiring mark_tokens() to have been called.
    Requires Python 3.8+. Doesn't support astroid.
    """
    start, end = self.get_text_range_unmarked(node)
    return self._text[start:end]


# Node types that check_get_text_unmarked should ignore. Only relevant for Python 3.8+.
_unsupported_unmarked_types = ()  # type: Tuple[Type[ast.AST], ...]
if sys.version_info[:2] >= (3, 8):
  _unsupported_unmarked_types += (
    # no lineno
    ast.arguments, ast.withitem,
  )
  if sys.version_info[:2] == (3, 8):
    _unsupported_unmarked_types += (
      # get_text_unmarked works incorrectly for these types due to bugs in Python 3.8.
      ast.arg, ast.Starred,
      # no lineno in 3.8
      ast.Slice, ast.ExtSlice, ast.Index, ast.keyword,
    )


def supports_unmarked(node=None):
  # type: (Any) -> bool
  return (
      isinstance(node, (ast.AST, type(None)))
      and not isinstance(node, _unsupported_unmarked_types)
      and sys.version_info[:2] >= (3, 8)
      and 'pypy' not in sys.version.lower()
  )
