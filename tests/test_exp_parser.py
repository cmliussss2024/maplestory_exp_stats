import unittest

from exp_parser import parse_exp


class ParseExpTests(unittest.TestCase):
    def test_reads_integer_after_exp_before_bracket(self):
        self.assertEqual(parse_exp("EXP 256163[87.07%]"), 256163)

    def test_returns_none_when_exp_missing(self):
        self.assertIsNone(parse_exp("HP 12345[10.00%]"))

    def test_returns_none_for_empty_text(self):
        self.assertIsNone(parse_exp(""))
