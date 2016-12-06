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

import bisect
import collections
import re
import token
import tokenize
from cStringIO import StringIO
#import textwrap

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
    return '%s:%r' % (token.tok_name[self.type], self.string)


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

  def get_token(self, offset):
    """
    Returns the token containing the given character offset (0-based position in code_text),
    or the preceeding token if the position is between tokens.
    """
    return self._tokens[bisect.bisect(self._token_offsets, offset) - 1]

  def next_token(self, token):
    """Returns the next token after the given one."""
    return self._tokens[token.index + 1]

  def prev_token(self, token):
    """Returns the previous token before the given one."""
    return self._tokens[token.index - 1]

  def token_range(self, first_token, last_token):
    """Yields all tokens in order from first_token through and including last_token."""
    for i in xrange(first_token.index, last_token.index + 1):
      yield self._tokens[i]
