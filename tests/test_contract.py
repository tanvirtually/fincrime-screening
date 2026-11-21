"""The committed output/dev.jsonl follows the output contract.

Run: python3 -m unittest tests/test_contract.py   (from the repo folder)
Needs no dataset, so it runs in CI.
"""
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "system"))
from main import FIELDS, REASONS_FOR, contract_problem, safe_row  # noqa: E402


class OutputContract(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(ROOT, "output", "dev.jsonl"), encoding="utf-8") as f:
            self.rows = [json.loads(line) for line in f]

    def test_every_line_is_valid(self):
        self.assertTrue(self.rows)
        for r in self.rows:
            with self.subTest(hit=r.get("hit_id")):
                self.assertEqual(tuple(r), FIELDS)
                self.assertIsNone(contract_problem(r))

    def test_one_line_per_hit(self):
        ids = [r["hit_id"] for r in self.rows]
        self.assertEqual(len(ids), len(set(ids)))

    def test_reason_codes_belong_to_one_decision(self):
        seen = set()
        for codes in REASONS_FOR.values():
            self.assertFalse(seen & codes)
            seen |= codes

    def test_broken_row_goes_to_review(self):
        bad = {"hit_id": "H-X", "alert_id": "A-X", "decision": "DIFFERENT_ENTITY",
               "reason_code": "NAME_DOB_MATCH", "customer_record_id": None, "reason": "x", "evidence": []}
        fixed = safe_row(bad)
        self.assertEqual(fixed["decision"], "REVIEW")
        self.assertIsNone(contract_problem(fixed))


if __name__ == "__main__":
    unittest.main()
