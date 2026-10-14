"""Regression for the standard-format versus local-model attribution boundary."""
import csv
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PHRASE = r"IEEE~754 specifies standard binary formats and rounding directions~\cite{ieee2019}."

class IeeeAttributionTests(unittest.TestCase):
    def test_contexts_preserve_precise_standard_attribution(self):
        with (ROOT / 'citation_contexts.csv').open(encoding='utf-8', newline='') as f:
            rows = [r for r in csv.DictReader(f) if r['source_file'] == 'paper/sections/boundaries.tex' and r['line_number'] == '3']
        self.assertTrue(rows)
        for row in rows:
            self.assertIn(PHRASE, row['context'])
            self.assertNotIn('fixes the formats and directions used here', row['context'])
        source = ROOT.parent / 'paper/sections/boundaries.tex'
        if source.exists():
            self.assertIn(PHRASE, source.read_text(encoding='utf-8'))

    def test_reading_scope_is_partial_and_version_qualified(self):
        with (ROOT / 'reference_audit.csv').open(encoding='utf-8', newline='') as f:
            row = next(r for r in csv.DictReader(f) if r['cite_key'] == 'ieee2019')
        self.assertIn('Selected examined-copy clauses', row['verification_scope'])
        self.assertIn('exact final-edition equivalence and full-standard review not certified', row['verification_scope'])

if __name__ == '__main__':
    unittest.main()
