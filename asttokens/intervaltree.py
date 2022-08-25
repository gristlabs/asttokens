from textwrap import indent
from operator import attrgetter
from bisect import bisect_right, bisect_left
import token


class IntervalTree:
  """
    The intervalTree is storing nested, consecutive interval in order to quickly
    query a location for the preceding/following opening or closing parenthesis.

    It only stores the index of the tokens that are []{} or ().

    Leaves nodes are always completely included in their parents.
    for example the following sequence, excluding non brackets.

    Note that is is not the generic interval tree, as child nodes are strictly
    included in their parents, and no two child overlap.

    Plus for efficiency and simplicity the child are dense, that is to say the
    c1.high == c2.low-1.


    We have 3 types of nodes:
    - The root – it has children, but an interval query should not extend to
      boundary.
    - IntervalTree node, represent a Pair of balanced bracket.
       - If the query contain a boundary, we extend the interval to the full
         node length and return.
       - If not, we recurse in children.
         - either both end of the query are included in a child
         - both ends are in different child.
    - EmptyNode nodes (leaves), are range of tokens that don't contain imbalanced
      brackets. When hitting those we don't need to extend the range.
      We _can_ have a tree without those nodes, but it ends up being more
      complicated and slower with the extra logic. Here we can just bisect
      children and recurse no matter what.


  """

  def __init__(self, low, high=float('inf')):
    self.low = low
    self.high = high
    # empty node well remove later, this make creating the tree easier as we
    # don't have to check whether children is empty in append.
    self.children = [EmptyNode(low,low)]
    self._low = []
    self._high = []


  def append(self, node):
    prev = self.children[-1]
    if node.low != prev.high+1:
      self.children.append(EmptyNode(prev.high+1, node.low-1))
    self.children.append(node)

  def finalize(self):
    """
    the tree is constructed, finalize it for faster query
    remove the Empty(low, low) from __init__, maybe append and empty
    node at eh end to have the children be dense (help edge cases with bisect
    queries) and precompute _low and _high, to avoid using
    `key=attributegetter(...)` in bisect with make bisect much slower.

    """

    for c in self.children:
      c.finalize()
    if self.children[-1].high < self.high -1:
      self.children.append(EmptyNode(self.children[-1].high+1, self.high-1))
    self.children.pop(0)
    self._low = [c.low for low in self.children]
    self._high = [c.high for low in self.children]

  def query_interval(self, low, high):
    """
    Find smaller encompassing interval that contains [low, high]

    For this type of node if one boundary is included, we can extend
    to the other boundary as an optimisation.

    For example:

        ( a + b + [ c ] * 3 )
        ^        ^high
        low                 ^
                            extend to there.
    """

    if low == self.low:
       return low, self.high
    if high == self.high:
       return self.low, high
    return self._query_interval(low, high)

  def _query_interval(self, low, high):
    """
    ... here we are strictly included recurse in children.


        ( a + b + [ c ] * 3 )
          ^         ^ high
         low

        we'll querry the "a + b +" node with low
        and the "[ c ]" range with high.
    """

    lowi = bisect_right(self._low, low)-1
    A = self.children[lowi]

    if high <= A.high:
      low, high = A.query_interval(low, high)
    else:
      hii = bisect_left(self._high, high)
      B = self.children[hii]
      low = A.query_low(low)
      high = B.query_high(high)
    return low, high


  def query_high(self, high):
    """
    We are in an imbalanced interval, return our max
    """
    return self.high

  def query_low(self, low):
    """
    We are in an imbalanced interval, return our min
    """
    return self.low

  def __repr__(self):
    rs = [repr(c) for c in self.children]
    ch = '\n'+indent( '\n'.join(rs), '  ') if rs else ''
    return f"{self.low}-{self.high}{ch}"

class Root(IntervalTree):

  def query_interval(self, low, high):
    """
    The root is the only node that has children
    but no matching pairs at both ends.
    So we do not skip the parent logic.
    """
    return self._query_interval(low, high)

class EmptyNode(IntervalTree):
  """
  No imbalanced bracket in this interval.
  """

  def __init__(self, low, high):
    self.low = low
    self.high = high

  def query_interval(self, low, high):
    return low, high

  def query_high(self, high):
    return high

  def query_low(self, low):
    return low

  def finalize(self):
    pass

  def __repr__(self):
    return f"{self.low}-{self.high} - Empty {self.high-self.low}"

def make_tree(toks):
  stack = [Root(0,len(toks))]
  for i,t in enumerate(toks):
    if t.type == token.OP:
      if t.string in '[{(':
        node = IntervalTree(i)
        stack[-1].append(node)
        stack.append(node)
      elif t.string in ']})':
        node = stack.pop()
        node.high = i
  assert len(stack) == 1
  root = stack[0]
  root.finalize()
  return root
