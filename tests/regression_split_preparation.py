"""Finite portable split regressions, outside the retained 28-test census."""
from bisect import bisect_left
from copy import deepcopy
from fractions import Fraction as Q
from itertools import product
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src import checker, phase, fixtures


def power(e):
    return Q(2 ** e) if e >= 0 else Q(1, 2 ** -e)


def tiny_case(mode, sign):
    return {'id': 'tiny-split-' + mode + ('-pos' if sign > 0 else '-neg'),
            'delta_exp': -4,
            'inputs': [{'name': 'x', 'format': {'p': 8, 'emin': -4, 'emax': 4},
                        'values': list(range(144, 160)) if sign > 0 else list(range(-159, -143))},
                       {'name': 'c', 'format': {'p': 8, 'emin': -4, 'emax': 4},
                        'values': [7 * sign]}],
            'gates': [{'kind': 'split', 'args': ['x', 'c'], 'out': ['s', 'r'],
                       'format': {'p': 4, 'emin': -4, 'emax': 4}, 'mode': mode,
                       'cell': {'kind': 'normal', 'exponent': 3, 'sign': sign},
                       'residual_format': {'p': 4, 'emin': -4, 'emax': 4}},
                      {'kind': 'add', 'args': ['s', 'r'], 'out': ['z'],
                       'format': {'p': 5, 'emin': -4, 'emax': 4}, 'mode': mode,
                       'cell': {'kind': 'normal', 'exponent': 3, 'sign': sign}}],
            'outputs': ['z'], 'cuts': [1]}


def literal_replay(case):
    """Enumerate literal finite values and derive complete phase/block relations."""
    grids = {}

    def rounded(value, fmt, mode):
        key = (fmt['p'], fmt['emin'], fmt['emax'])
        if key not in grids:
            p, emin, emax = key
            values = {Q(0)}
            values.update(n * power(emin - p + 1) for n in range(1, 2 ** (p - 1)))
            for e in range(emin, emax + 1):
                values.update(n * power(e - p + 1) for n in range(2 ** (p - 1), 2 ** p))
            grids[key] = sorted(values | {-v for v in values})
        values = grids[key]
        j = bisect_left(values, value)
        if j < len(values) and values[j] == value:
            return value
        if not 0 < j < len(values):
            raise ValueError('literal finite envelope')
        a, b = values[j - 1], values[j]
        if mode == 'rdn' or mode == 'rtz' and value >= 0:
            return a
        if mode == 'rup' or mode == 'rtz':
            return b
        if value - a != b - value:
            return a if value - a < b - value else b
        return a if (a / (b - a)).numerator % 2 == 0 else b

    delta = power(case['delta_exp'])
    periods = []
    for gate in case['gates']:
        m = int(power(gate['cell']['exponent'] - gate['format']['p'] + 1) / delta)
        periods.append(2 * m if gate['mode'] == 'rne' and m > 1 else m)
    modulus = max(periods)
    global_rows, maps = {}, [{} for _ in case['gates']]
    names = [item['name'] for item in case['inputs']]
    ports = []
    for inputs in product(*(item['values'] for item in case['inputs'])):
        state = {n: v * delta for n, v in zip(names, inputs)}
        start_sum, loss = sum(state.values(), Q(0)), Q(0)
        local_ports = []
        for index, gate in enumerate(case['gates']):
            incoming = sorted(state)
            key = tuple(int(state[n] / delta) % modulus for n in incoming)
            argument = sum((state.pop(n) for n in gate['args']), Q(0))
            q = rounded(argument, gate['format'], gate['mode'])
            residual = argument - q
            state[gate['out'][0]] = q
            increment = Q(0) if gate['kind'] == 'split' else residual
            if gate['kind'] == 'split':
                if rounded(residual, gate['residual_format'], 'rne') != residual:
                    raise ValueError('literal split residual')
                state[gate['out'][1]] = residual
            loss += increment
            outgoing = sorted(state)
            value = (tuple(int(state[n] / delta) % modulus for n in outgoing), int(increment / delta))
            if key in maps[index] and maps[index][key] != value:
                raise ValueError('literal block is not phase functional')
            maps[index][key] = value
            local_ports.append((incoming, outgoing))
        if start_sum - sum(state.values(), Q(0)) != loss:
            raise ValueError('literal conservation')
        ports = local_ports
        key = tuple(v % modulus for v in inputs)
        global_rows[key] = (tuple(int(state[n] / delta) % modulus for n in case['outputs']), int(loss / delta))
    rows = lambda mapping: [{'in': list(k), 'out': list(v[0]), 'loss': v[1]}
                            for k, v in sorted(mapping.items())]
    blocks = [{'begin': i, 'end': i + 1, 'in_names': ports[i][0], 'out_names': ports[i][1],
               'rows': rows(mapping)} for i, mapping in enumerate(maps)]
    return modulus, rows(global_rows), blocks


def selected_cases():
    cases = [c for c in fixtures.suite() if c['id'].startswith(('split-', 'deep-split-'))
             or c['id'] == 'phase-loss-correlation']
    base = next(c for c in cases if c['id'] == 'deep-split-positive-32')
    for i, cuts in enumerate(([], base['cuts'], list(range(1, 32)), [1, 3, 7, 12, 18, 25, 31])):
        current = deepcopy(base)
        current['id'], current['cuts'] = 'preparation-cut-' + str(i), list(cuts)
        cases.append(current)
    cases.extend(tiny_case(mode, sign) for mode in ('rne', 'rup', 'rdn', 'rtz') for sign in (1, -1))
    return cases


def capped_cases():
    wide = tiny_case('rne', 1)
    wide['delta_exp'] = -2049
    rows = {'id': 'row-cap', 'delta_exp': -4,
            'inputs': [{'name': n, 'format': {'p': 16, 'emin': -4, 'emax': 8},
                        'values': list(range(128, 256))} for n in ('x', 'y')],
            'gates': [], 'outputs': ['x', 'y'], 'cuts': []}
    gates = deepcopy(rows)
    gates['inputs'] = gates['inputs'][:1]
    gates['inputs'][0]['values'] = [128]
    gates['outputs'] = ['s64']
    gates['gates'] = [{'kind': 'cast', 'args': ['x' if i == 0 else 's' + str(i - 1)],
                      'out': ['s' + str(i)], 'format': {'p': 8, 'emin': -4, 'emax': 4},
                      'mode': 'rne', 'cell': {'kind': 'normal', 'exponent': 3, 'sign': 1}}
                     for i in range(65)]
    depth = deepcopy(gates)
    depth['gates'] = depth['gates'][:33]
    depth['outputs'] = ['s32']
    return [wide, rows, gates, depth]


def snapshot():
    # Only pure helpers are called; the private Windows comparison denies resource operations.
    from src import campaign
    certificates, checks = [], []
    for case in selected_cases():
        cert = checker.normalize(phase.build(case))
        for key in checker.COUNTS:
            checker.COUNTS[key] = 0
        result = checker.check(case, cert)
        certificates.append(cert)
        checks.append({'result': result, 'counts': dict(checker.COUNTS)})
    rejected = []
    for case in fixtures.unsupported_suite() + capped_cases():
        try:
            phase.build(case)
        except ValueError as error:
            rejected.append([case['id'], type(error).__name__, str(error)])
        else:
            rejected.append([case['id'], 'accepted'])
    case = fixtures.chain('positive-rne-rne', range(128, 160), 7, 8)
    mutations = campaign.mutate(case, checker.normalize(phase.build(case)))
    case = next(c for c in fixtures.suite() if c['id'] == 'correlated-inputs')
    cert = checker.normalize(phase.build(case))
    case.pop('relation')
    cert['network'] = deepcopy(case)
    cert['meta'] = checker.normalize(checker.prepare(case))
    try:
        checker.check(case, cert)
    except ValueError as error:
        mutations.append({'mutation': 'correlation-erased-stale-contract',
                          'rejected': True, 'reason': str(error)})
    return {'certificates': certificates, 'checker_results_and_counts': checks,
            'unsupported_and_caps': rejected, 'retained_mutations': mutations}


class SplitPreparationRegression(unittest.TestCase):
    def test_literal_enumeration_and_retained_certificates(self):
        for mode in ('rne', 'rup', 'rdn', 'rtz'):
            for sign in (1, -1):
                case = tiny_case(mode, sign)
                cert = checker.normalize(phase.build(case))
                modulus, rows, blocks = literal_replay(case)
                self.assertEqual(cert['meta']['modulus_units'], modulus)
                self.assertEqual(cert['rows'], rows)
                self.assertEqual(cert['blocks'], blocks)
                checker.check(case, cert)
        retained = json.loads((ROOT / 'results' / 'certificates.json').read_text(encoding='utf-8'))
        by_id = {item['network']['id']: item for item in retained}
        projections = []
        for case in selected_cases():
            cert = checker.normalize(phase.build(case))
            checker.check(case, cert)
            if case['id'] in by_id:
                self.assertTrue(checker.strict_equal(cert, by_id[case['id']]))
            if case['id'].startswith('preparation-cut-'):
                projections.append((cert['rows'], cert['max_abs_loss_units'], cert['tight_power_two_exponent']))
        self.assertEqual(len(projections), 4)
        self.assertTrue(all(p == projections[0] for p in projections))

    def test_build_local_formats_reached_checks_and_standalone_transfer(self):
        case = tiny_case('rne', 1)
        original = checker.normalize(phase.build(case))
        changed = deepcopy(case)
        changed['gates'][0]['residual_format'] = {'p': 3, 'emin': -3, 'emax': 4}
        checker.check(changed, checker.normalize(phase.build(changed)))
        with self.assertRaises(ValueError):
            checker.check(changed, original)
        changed['gates'][0]['residual_format'] = {'p': 2, 'emin': 0, 'emax': 4}
        with self.assertRaisesRegex(ValueError, 'unrepresentable exact residual'):
            phase.build(changed)
        self.assertEqual(checker.normalize(phase.build(case)), original)
        meta, info, modulus = phase.validate(case)
        for x in case['inputs'][0]['values']:
            state = {'x': x % modulus, 'c': 7 % modulus}
            loss = phase.step(case, case['gates'][0], info[0], state, 0, modulus)
            self.assertEqual(loss, 0)
        for rejected in fixtures.unsupported_suite() + capped_cases():
            with self.assertRaises(ValueError):
                phase.build(rejected)

    def test_constant_reads_are_local_but_representability_is_per_transfer(self):
        case = tiny_case('rne', 1)
        reads, represents = [], []
        original_read, original_represents = phase.Format.read, phase.Format.represents

        def read(data):
            reads.append(data)
            return original_read(data)

        def represents_value(fmt, value):
            represents.append((fmt, value))
            return original_represents(fmt, value)

        with patch.object(phase.Format, 'read', side_effect=read), \
                patch.object(phase.Format, 'represents', represents_value):
            cert = phase.build(case)
        residual_data = case['gates'][0]['residual_format']
        self.assertEqual(sum(data is residual_data for data in reads), 2)  # validation + preparation
        residual_format = original_read(residual_data)
        self.assertEqual(sum(fmt == residual_format for fmt, _ in represents),
                         len(cert['blocks'][0]['rows']))
        checker.check(case, checker.normalize(cert))


if __name__ == '__main__':
    unittest.main()
