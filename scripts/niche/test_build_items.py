"""python3 -m unittest discover -s scripts/niche"""
import unittest

import build_items as b


class BuildItemsTest(unittest.TestCase):
    def test_reference_cleanup_drops_titles_and_junk(self):
        self.assertEqual(b.clean_ref(" 126610ln "), "126610LN")
        self.assertEqual(b.clean_ref("01 400 7778 7158-07 7 20 01TLC"), "01 400 7778 7158-07 7 20 01TLC")
        self.assertEqual(b.clean_ref("Unknown"), "")
        self.assertEqual(b.clean_ref("Rolex Daytona Oysterflex 116515LN Rosegold"), "")

    def test_long_reference_matches_its_leading_parts(self):
        self.assertEqual(b.ref_prefixes("15300ST.OO.1220ST.02"), ["15300stoo1220st02", "15300stoo1220st", "15300stoo", "15300st"])

    def test_values_become_keys(self):
        self.assertEqual(b.value_key("Crocodile-Leather"), "crocodile_leather")
        self.assertEqual(b.value_key("Champaign"), "champagne")

    def test_complications_come_from_the_model_name(self):
        self.assertEqual(b.complications("Day-Date 40"), ["day_date"])
        self.assertEqual(b.complications("Navitimer B01 Chronograph 43"), ["chronograph"])
        self.assertEqual(b.complications("Royal Oak Perpetual Calendar"), ["perpetual_calendar"])

    def test_years_and_sizes(self):
        self.assertEqual(b.year_of("2019"), 2019)
        self.assertIsNone(b.year_of("1970 (Approximation)"))
        self.assertEqual(b.size_of("42 mm"), 42.0)
        self.assertIsNone(b.size_of("5 mm"))


if __name__ == "__main__":
    unittest.main()
