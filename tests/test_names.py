"""Name and country edge cases: Irish, Bengali, Nepali, Tamil / Sri Lankan.

Run: python3 -m unittest tests/test_names.py   (from the repo folder)

Each case says whether two names should agree under POLICY.md principle 8.
"Agree" means the hit can't be cleared on name, so a wrong "disagree" is the
dangerous direction: it can clear a real match.
"""
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "system"))
import countries  # noqa: E402
import names  # noqa: E402

VARIANTS = os.path.join(ROOT, "dev", "name_variants.json")
if os.path.exists(VARIANTS):
    with open(VARIANTS, encoding="utf-8") as f:
        data = json.load(f)
    names.load_variants(data["groups"], data.get("company_legal_forms"))
else:
    names.load_variants([["muhammad", "mohammed", "mohammad", "mohamed", "mohd"]])

AGREE = [
    # Irish O' and Mac names, written every way
    ("Sean O'Brien", "Sean OBrien"),
    ("Sean O'Brien", "Sean O Brien"),
    ("Sean O’Brien", "SEAN OBRIEN"),           # curly apostrophe
    ("Siobhan O'Dea", "Siobhan ODea"),             # short surname after O'
    ("Siobhan O'Dea", "Siobhan O Dea"),
    ("Mary O'Neill", "O'NEILL, Mary"),             # surname-first listing
    ("Ciaran McDonald", "Ciaran MacDonald"),
    ("Ciaran McDonald", "Ciaran Mc Donald"),
    ("Aoife Ni Bhriain", "Aoife Ní Bhriain"),  # fada
    ("Padraig O Suilleabhain", "Pádraig Ó Súilleábháin"),
    # Bengali / South Asian Muslim names: Md, Mohd, Muhammad
    ("Md Karim", "Mohammed Karim"),
    ("MD. Abdul Karim", "Mohammad Abdul Karim"),
    ("Mohd Rafiqul Islam", "Md Rafiqul Islam"),
    ("Muhammad Shahidul Islam", "Shahidul Islam"),
    ("Md Nazrul Islam", "Nazrul Islam"),
    ("Abul Kalam Azad", "Abul Kalam"),
    ("Sheikh Mujibur Rahman", "Mujibur Rahman"),
    ("Mohammed Jasim Uddin", "Md Jasim Ud Din"),   # Uddin written apart
    # Nepali names
    ("Ram Bahadur Thapa", "Ram Bahadur Thapa Magar"),
    ("Pushpa Kamal Dahal", "Dahal, Pushpa Kamal"),
    ("Sher Bahadur Deuba", "Sher Bahadur Deuwa"),  # spelling variant
    # Tamil / Sri Lankan names: initials, father's name first or last
    ("S. Sivakumar", "Sivakumar Selvaratnam"),
    ("Velupillai Prabhakaran", "V. Prabhakaran"),
    ("K. R. Selvarajah", "Selvarajah"),
    ("Thirunavukkarasu Murugan", "Thirunavukarasu Murugan"),
    ("Ranasinghe Arachchige Dissanayake", "Dissanayake Ranasinghe"),
]

DISAGREE = [
    # Shared common parts alone must not make two different people agree
    ("Md Karim", "Md Rahman"),
    ("Mohammed Karim", "Mohammed Hossain"),
    ("Ram Bahadur Thapa", "Hari Prasad Sharma"),
    ("Sean O'Brien", "Sean Kelly"),
    ("S. Sivakumar", "S. Rajaratnam"),
]

COUNTRIES = [
    ("Eire", "Ireland"),
    ("Republic of Ireland", "Ireland"),
    ("Irish", "Ireland"),
    ("Northern Ireland", "United Kingdom"),
    ("Ceylon", "Sri Lanka"),
    ("Sri Lankan", "Sri Lanka"),
    ("LK", "Sri Lanka"),
    ("Nepali", "Nepal"),
    ("Nepalese", "Nepal"),
    ("Bangladeshi", "Bangladesh"),
    ("BD", "Bangladesh"),
    ("Kathmandu, Bagmati, Nepal", "Nepal"),
    ("Jaffna, Northern Province, Sri Lanka", "Sri Lanka"),
    ("Dhaka, Bangladesh", "Bangladesh"),
]


class NameEdgeCases(unittest.TestCase):
    def test_agree(self):
        for a, b in AGREE:
            with self.subTest(a=a, b=b):
                self.assertTrue(names.names_agree(a, b), f"{a!r} vs {b!r} should agree")

    def test_disagree(self):
        for a, b in DISAGREE:
            with self.subTest(a=a, b=b):
                self.assertFalse(names.names_agree(a, b), f"{a!r} vs {b!r} should not agree")

    def test_countries(self):
        for raw, want in COUNTRIES:
            with self.subTest(raw=raw):
                self.assertEqual(countries.norm(raw), want)


if __name__ == "__main__":
    unittest.main()
