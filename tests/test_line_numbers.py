# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import unittest
from .context import asttokens

class TestLineNumbers(unittest.TestCase):

  def test_line_numbers(self):
    ln = asttokens.LineNumbers("Hello\nworld\nThis\n\nis\n\na test.\n")
    self.assertEqual(ln.line_to_offset(1, 0), 0)
    self.assertEqual(ln.line_to_offset(1, 5), 5)
    self.assertEqual(ln.line_to_offset(2, 0), 6)
    self.assertEqual(ln.line_to_offset(2, 5), 11)
    self.assertEqual(ln.line_to_offset(3, 0), 12)
    self.assertEqual(ln.line_to_offset(4, 0), 17)
    self.assertEqual(ln.line_to_offset(5, 0), 18)
    self.assertEqual(ln.line_to_offset(6, 0), 21)
    self.assertEqual(ln.line_to_offset(7, 0), 22)
    self.assertEqual(ln.line_to_offset(7, 7), 29)
    self.assertEqual(ln.offset_to_line(0),  (1, 0))
    self.assertEqual(ln.offset_to_line(5),  (1, 5))
    self.assertEqual(ln.offset_to_line(6),  (2, 0))
    self.assertEqual(ln.offset_to_line(11), (2, 5))
    self.assertEqual(ln.offset_to_line(12), (3, 0))
    self.assertEqual(ln.offset_to_line(17), (4, 0))
    self.assertEqual(ln.offset_to_line(18), (5, 0))
    self.assertEqual(ln.offset_to_line(21), (6, 0))
    self.assertEqual(ln.offset_to_line(22), (7, 0))
    self.assertEqual(ln.offset_to_line(29), (7, 7))

    # Test that out-of-bounds inputs still return something sensible.
    self.assertEqual(ln.line_to_offset(6, 19), 30)
    self.assertEqual(ln.line_to_offset(100, 99), 30)
    self.assertEqual(ln.line_to_offset(2, -1), 6)
    self.assertEqual(ln.line_to_offset(-1, 99), 0)
    self.assertEqual(ln.offset_to_line(30), (8, 0))
    self.assertEqual(ln.offset_to_line(100), (8, 0))
    self.assertEqual(ln.offset_to_line(-100), (1, 0))

  def test_unicode(self):
    ln = asttokens.LineNumbers("фыва\nячсм")
    self.assertEqual(ln.line_to_offset(1, 0), 0)
    self.assertEqual(ln.line_to_offset(1, 4), 4)
    self.assertEqual(ln.line_to_offset(2, 0), 5)
    self.assertEqual(ln.line_to_offset(2, 4), 9)

    self.assertEqual(ln.offset_to_line(0), (1, 0))
    self.assertEqual(ln.offset_to_line(4), (1, 4))
    self.assertEqual(ln.offset_to_line(5), (2, 0))
    self.assertEqual(ln.offset_to_line(9), (2, 4))

  def test_utf8_offsets(self):
    ln = asttokens.LineNumbers("фыва\nф.в.")
    self.assertEqual(ln.from_utf8_col(1, 0), 0)
    self.assertEqual(ln.from_utf8_col(1, 2), 1)
    self.assertEqual(ln.from_utf8_col(1, 3), 1)
    self.assertEqual(ln.from_utf8_col(1, 6), 3)
    self.assertEqual(ln.from_utf8_col(1, 8), 4)
    self.assertEqual(ln.from_utf8_col(2, 0), 0)
    self.assertEqual(ln.from_utf8_col(2, 2), 1)
    self.assertEqual(ln.from_utf8_col(2, 3), 2)
    self.assertEqual(ln.from_utf8_col(2, 4), 2)
    self.assertEqual(ln.from_utf8_col(2, 5), 3)
    self.assertEqual(ln.from_utf8_col(2, 6), 4)
