import asttokens
import unittest

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


