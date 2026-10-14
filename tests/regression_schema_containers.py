"""Supplementary checks of the public JSON container schema."""
from copy import deepcopy
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src import checker, phase


def valid_case():
    return {'id': 'single-wire-array-control', 'delta_exp': -4,
            'inputs': [{'name': 'x', 'format': {'p': 8, 'emin': -4, 'emax': 4},
                        'values': [128]}],
            'gates': [{'kind': 'cast', 'args': ['x'], 'out': ['s'],
                       'format': {'p': 4, 'emin': -4, 'emax': 4},
                       'mode': 'rne', 'cell': {'kind': 'normal', 'exponent': 3, 'sign': 1}}],
            'outputs': ['s'], 'cuts': []}


class ContainerContract(unittest.TestCase):
    def rejected_at_both_entries(self, value):
        with self.assertRaises(ValueError):
            phase.build(value)
        with self.assertRaises(ValueError):
            checker.prepare(value)

    def test_literal_valid_case_and_relation(self):
        case = valid_case()
        certificate = checker.normalize(phase.build(case))
        checker.check(case, certificate)
        self.assertEqual(certificate['max_abs_loss_units'], 0)
        case['relation'] = [[128]]
        checker.check(case, checker.normalize(phase.build(case)))

    def test_single_wire_strings_are_not_arrays(self):
        for field, replacement in (('args', 'x'), ('out', 's')):
            with self.subTest(field=field):
                case = valid_case()
                case['gates'][0][field] = replacement
                self.rejected_at_both_entries(case)
        case = valid_case()
        case['outputs'] = 's'
        self.rejected_at_both_entries(case)

    def test_non_array_container_fields(self):
        for field in ('inputs', 'gates', 'outputs', 'cuts'):
            with self.subTest(field=field):
                case = valid_case()
                case[field] = tuple(case[field])
                self.rejected_at_both_entries(case)
        case = valid_case()
        case['inputs'][0]['values'] = (128,)
        self.rejected_at_both_entries(case)
        for relation in (([128],), [(128,)]):
            case = valid_case()
            case['relation'] = deepcopy(relation)
            self.rejected_at_both_entries(case)

    def test_wrong_object_shapes_fail_with_value_error(self):
        self.rejected_at_both_entries(None)
        for target in ('input', 'gate', 'cell'):
            case = valid_case()
            if target == 'input':
                case['inputs'][0] = None
            elif target == 'gate':
                case['gates'][0] = None
            else:
                case['gates'][0]['cell'] = None
            self.rejected_at_both_entries(case)


if __name__ == '__main__':
    unittest.main(verbosity=2)
