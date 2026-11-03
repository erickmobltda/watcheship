"""python3 -m unittest discover -s scripts/niche"""
import unittest

import build_items as b


class BuildItemsTest(unittest.TestCase):
    def test_reference_cleanup_drops_titles_and_junk(self):
        self.assertEqual(b.clean_ref(" 126610ln "), "126610LN")
        self.assertEqual(b.clean_ref("01 400 7778 7158-07 7 20 01TLC"), "01 400 7778 7158-07 7 20 01TLC")
        self.assertEqual(b.clean_ref("Unknown"), "")
        self.assertEqual(b.clean_ref("Rolex Daytona Oysterflex 116515LN Rosegold"), "")

    def test_seller_notes_are_cut_from_the_reference(self):
        self.assertEqual(b.clean_ref("116500LN -- 05-2017"), "116500LN")
        self.assertEqual(b.clean_ref("116503 FULL SET"), "116503")
        self.assertEqual(b.clean_ref("126610LV-MK II (NEW"), "126610LV-MK II")
        self.assertEqual(b.clean_ref("5167R- 001"), "5167R-001")

    def test_colour_and_strap_variants_share_a_base_reference(self):
        self.assertEqual(b.base_ref("Rolex", "116500LN-0001"), "116500LN")
        self.assertEqual(b.base_ref("Rolex", "116500LN 0523"), "116500LN")
        self.assertEqual(b.base_ref("Omega", "210.30.42.20.01.001"), "210.30.42.20")
        self.assertEqual(b.base_ref("Audemars Piguet", "25721ST.OO.1000ST.01"), "25721ST")
        self.assertEqual(b.base_ref("TAG Heuer", "WAZ111A-BA0875"), "WAZ111A")
        self.assertEqual(b.base_ref("Patek Philippe", "5196G-001"), "5196G")
        self.assertEqual(b.base_ref("Breitling", "AB0138211B1P1"), "AB0138")
        self.assertEqual(b.base_ref("Seiko", "SBDC061"), "SBDC061")

    def test_model_line_and_its_size(self):
        self.assertEqual(b.line_name("Datejust 41"), "Datejust")
        self.assertEqual(b.line_name("Navitimer 01 (46 MM)"), "Navitimer 01")
        self.assertEqual(b.line_name("5 Sports"), "5 Sports")
        self.assertEqual(b.size_of_ref({"model": "Datejust 41", "caseSize": 36.0}), 41)
        self.assertEqual(b.size_of_ref({"model": "Daytona", "caseSize": 40.0}), 40)

    def test_collection_only_brands_take_the_line_from_the_reference(self):
        self.assertEqual(b.ref_line("Casio", "GA-2100-1A1ER"), "GA-2100")
        self.assertEqual(b.ref_line("Casio", "GR-B300-1A"), "GR-B300")
        self.assertEqual(b.ref_line("Seiko", "SRPF67K1"), "SRPF67")
        self.assertEqual(b.ref_line("Citizen", "NB6021-68L"), "NB6021")
        self.assertIsNone(b.ref_line("Rolex", "126610LN"))

    def test_hand_added_watches_are_in_the_catalog(self):
        self.assertIn("casio-gr-b300-1a", {i["key"] for i in b.build()})

    def test_one_item_per_line_and_main_size(self):
        names = {i["name"] for i in b.build()}
        self.assertTrue({"Rolex Datejust 36 mm", "Rolex Datejust 41 mm"} <= names)
        self.assertFalse(any(n.startswith("Rolex Datejust 116") for n in names))

    def test_every_key_is_unique_and_samples_keep_theirs(self):
        items = b.build()
        keys = [i["key"] for i in items]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertTrue({"rolex-126610ln", "omega-310-30-42-50-01-001", "casio-f91w"} <= set(keys))

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
