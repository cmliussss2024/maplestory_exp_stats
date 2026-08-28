import unittest

from exp_parser import parse_exp, pick_exp


class ParseExpTests(unittest.TestCase):
    def test_reads_integer_after_exp_before_bracket(self):
        self.assertEqual(parse_exp("EXP 256163[87.07%]"), 256163)

    def test_returns_none_when_exp_missing(self):
        self.assertIsNone(parse_exp("HP 12345[10.00%]"))

    def test_returns_none_for_empty_text(self):
        self.assertIsNone(parse_exp(""))

    def test_joins_spaces_inside_the_integer(self):
        self.assertEqual(parse_exp("EXP 67 106[20.70%]"), 67106)

    def test_accepts_truncated_exp_prefix(self):
        self.assertEqual(parse_exp("XP 67106[20.70%]"), 67106)

    def test_strips_percent_when_opening_bracket_is_missing(self):
        self.assertEqual(parse_exp("EXP 6710620.709]"), 67106)

    def test_treats_ocr_sui_as_percent(self):
        self.assertEqual(parse_exp("XP 67106[20.70岁]"), 67106)

    def test_accepts_dash_inside_percent(self):
        self.assertEqual(parse_exp("EXP 68679[21-18%]"), 68679)

    def test_ignores_leading_garbage_before_exp(self):
        self.assertEqual(parse_exp("、EXP 67106[20.70%]"), 67106)

    def test_does_not_treat_clipped_epb_as_a_huge_number(self):
        self.assertIsNone(parse_exp("EPB710820 70岁]"))


class PickExpTests(unittest.TestCase):
    def test_prefers_bracketed_reading_over_swallowed_percent(self):
        self.assertEqual(
            pick_exp(
                [
                    ("EXP 68957212724]", 0.77),
                    ("EXP 68957[21.27%]", 0.83),
                ]
            ),
            68957,
        )

    def test_returns_none_when_every_reading_fails(self):
        self.assertIsNone(pick_exp([("HP 12", 0.9), ("", 0.1)]))
