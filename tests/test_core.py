"""Finite tests, separate from the paper's parameterized mathematical proofs."""
from fractions import Fraction as F
from copy import deepcopy
import ast
import json
from pathlib import Path
import unittest
from src import checker
from src.semantics import Format,two,lattice_round
from src.phase import build
from src.campaign import (census_audit, structural_challenge_audit, residual_periods,
                          rounding_oracle_audit, signatures)
from src.fixtures import (chain,fmt,suite,tiny_network_census,
                          structural_challenge_suite,unsupported_suite)

class ExactSemantics(unittest.TestCase):
    def test_three_rounding_paths_agree(self):
        # Explicit sorted-format oracle, neighboring-value checker, integer producer.
        f=fmt(3,-2,3);vals=checker.explicit_values(f);fast=Format.read(f)
        for numerator in range(-224,225):
            x=F(numerator,16)
            for mode in ('rne','rup','rdn','rtz'):
                ref=checker.explicit_round(x,vals,mode)
                self.assertEqual(checker.round_value(x,f,mode),ref)
                self.assertEqual(fast.round(x,mode),ref)

    def test_all_small_format_gap_rounding_oracles(self):
        result=rounding_oracle_audit()
        self.assertEqual(result['formats'],4)
        self.assertEqual(result['comparisons'],4224)
    def test_negative_ties_and_subnormals(self):
        f=Format(3,0,3)
        for x,want in [(F(1,8),F(0)),(F(3,8),F(1,2)),(F(-1,8),F(0)),(F(-3,8),F(-1,2))]:
            self.assertEqual(f.round(x),want)
    def test_lattice_period_and_missing_parity(self):
        for m in (2,4,8,16):
            for x in range(-2*m,2*m):
                self.assertEqual(lattice_round(x+2*m,m,'rne')-lattice_round(x,m,'rne'),2*m)
                self.assertEqual(abs(x-lattice_round(x,m,'rne')),abs(x+m-lattice_round(x+m,m,'rne')))
            self.assertNotEqual(lattice_round(m//2,m,'rne')-m//2,
                                lattice_round(3*m//2,m,'rne')-3*m//2)
    def test_nearest_exact_identity(self):
        c={'id':'empty-identity','delta_exp':-4,'inputs':[{'name':'x','format':fmt(8),'values':[128,129]}],
           'gates':[],'outputs':['x'],'cuts':[]}
        p=build(c);checker.check(c,checker.normalize(p));self.assertEqual(p['max_abs_loss_units'],0)
    def test_split_conservation_and_drain(self):
        c=next(c for c in suite() if c['id']=='split-drain')
        p=checker.normalize(build(c));result=checker.check(c,p)
        self.assertEqual(result['max_abs_loss_units'],8)
        self.assertEqual(result['max_depth'],2)
        c=next(c for c in suite() if c['id']=='ordinary-drain')
        p=checker.normalize(build(c));self.assertEqual(checker.check(c,p)['max_depth'],1)
    def test_retains_input_relation(self):
        cs={c['id']:c for c in suite()}
        correlated=build(cs['correlated-inputs']);marginal=build(cs['marginal-inputs'])
        self.assertEqual(correlated['max_abs_loss_units'],16)
        self.assertEqual(marginal['max_abs_loss_units'],31)
    def test_retains_phase_loss_relation(self):
        c=next(c for c in suite() if c['id']=='phase-loss-correlation')
        p=checker.normalize(build(c));checker.check(c,p)
        self.assertEqual(p['max_abs_loss_units'],4)
        self.assertEqual(p['tight_power_two_exponent'],-2)
    def test_fail_closed_boundaries(self):
        for c in unsupported_suite():
            with self.subTest(c=c['id']):
                with self.assertRaises(ValueError):build(c)
    def test_strict_certificate_integer_types(self):
        c=chain('strict-row',[128],0,0);p=checker.normalize(build(c))
        p['rows'][0]['loss']=False
        with self.assertRaises(ValueError):checker.check(c,p)
    def test_duplicate_json_keys_rejected(self):
        with self.assertRaises(ValueError):checker.unique_object([('x',1),('x',2)])

    def test_nonfinite_json_constants_rejected(self):
        for text in ('NaN','Infinity','-Infinity'):
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    json.loads(text,parse_constant=checker.bad_constant)
    def test_tampered_bound_rejected(self):
        c=chain('bound-control',range(128,160),7,8)
        p=checker.normalize(build(c));p['max_abs_loss_units']-=1
        with self.assertRaises(ValueError):checker.check(c,p)
    def test_integer_types(self):
        c=chain('bad-type',[128],7,8);c['delta_exp']=False
        with self.assertRaises(ValueError):build(c)
    def test_cut_change_recomputes_same_result(self):
        c=chain('cut-control',range(128,160),7,8)
        p=build(c);c['cuts']=[];q=build(c)
        self.assertEqual(p['rows'],q['rows'])
    def test_mode_change_must_rebuild_certificate(self):
        c=chain('mode-control',range(128,160),7,8);p=checker.normalize(build(c))
        d=deepcopy(c);d['gates'][0]['mode']='rup';p['network']=d
        with self.assertRaises(ValueError):checker.check(d,p)

    def test_checker_is_source_independent_of_producer(self):
        tree=ast.parse(Path(checker.__file__).read_text())
        imported=[]
        for node in ast.walk(tree):
            if isinstance(node,ast.Import): imported.extend(alias.name for alias in node.names)
            elif isinstance(node,ast.ImportFrom): imported.append(node.module or '')
        self.assertFalse(any(name.startswith('src') for name in imported),imported)

    def test_complete_tiny_network_census_axes(self):
        cases=tiny_network_census()
        self.assertEqual(len(cases),864)
        self.assertEqual(len({c['id'] for c in cases}),864)
        rows=[checker.check(c,checker.normalize(build(c))) for c in cases]
        audit=census_audit(cases,rows)
        self.assertEqual(audit['concrete_input_rows'],6912)
        self.assertEqual(audit['max_depth'],2)

    def test_structural_challenge_axes(self):
        cases=structural_challenge_suite()
        self.assertEqual(len(cases),320)
        self.assertEqual(len({c['id'] for c in cases}),320)
        rows=[checker.check(c,checker.normalize(build(c))) for c in cases]
        audit=structural_challenge_audit(cases,rows)
        self.assertEqual(audit['concrete_input_rows'],5120)
        self.assertEqual((audit['max_gates'],audit['max_depth']),(3,3))
        self.assertEqual(set(audit['dimensions']['cell_regimes']),{'normal','subnormal'})

    def test_independent_network_oracle_import_isolation(self):
        path=Path(__file__).resolve().parents[1]/'independent_oracle.py'
        tree=ast.parse(path.read_text())
        imported=[]
        for node in ast.walk(tree):
            if isinstance(node,ast.Import): imported.extend(alias.name for alias in node.names)
            elif isinstance(node,ast.ImportFrom): imported.append(node.module or '')
        self.assertFalse(any(name.startswith('src') for name in imported),imported)

    def test_production_sources_do_not_depend_on_assert(self):
        root=Path(__file__).resolve().parents[1]
        paths=list((root/'src').glob('*.py'))+[root/'independent_oracle.py']
        offenders=[]
        for path in paths:
            tree=ast.parse(path.read_text())
            if any(isinstance(node,ast.Assert) for node in ast.walk(tree)):
                offenders.append(path.name)
        self.assertEqual(offenders,[])

    def test_depth_32_mixed_split_chain(self):
        c=next(c for c in suite() if c['id']=='deep-split-positive-32')
        p=checker.normalize(build(c));result=checker.check(c,p)
        self.assertEqual((result['gates'],result['max_depth']),(32,32))
        self.assertGreaterEqual(result['formats'],3)

    def test_seven_level_serial_accumulation(self):
        c=next(c for c in suite() if c['id']=='serial-negative-3')
        p=checker.normalize(build(c));result=checker.check(c,p)
        self.assertEqual((result['gates'],result['max_depth']),(7,7))
        self.assertEqual(result['input_rows'],32)

    def test_balanced_eight_input_topology(self):
        c=next(c for c in suite() if c['id']=='balanced-positive-2')
        p=checker.normalize(build(c));result=checker.check(c,p)
        self.assertEqual((result['gates'],result['max_depth']),(7,3))
        self.assertEqual(result['input_rows'],256)

    def test_cut_partition_invariance_at_depth_32(self):
        base=next(c for c in suite() if c['id']=='deep-split-positive-32')
        projections=[]
        for cuts in ([],base['cuts'],list(range(1,32)),[1,3,7,12,18,25,31]):
            c=deepcopy(base);c['cuts']=list(cuts)
            p=checker.normalize(build(c));checker.check(c,p)
            projections.append((p['rows'],p['max_abs_loss_units'],p['tight_power_two_exponent']))
        self.assertTrue(all(x==projections[0] for x in projections[1:]))

    def test_least_residual_periods_all_modes(self):
        result=residual_periods()
        self.assertEqual(result['configurations'],35)
        self.assertEqual(result['total_checks'],3770)
        for row in result['rows']:
            m=row['spacing_units'];mode=row['mode']
            want=1 if m==1 else (2*m if mode=='nearest-even' else m)
            self.assertEqual(row['least_period_units'],want)

    def test_mode_sensitive_alphabet_sharpness(self):
        # Directed one-addition contexts distinguish m phases by exactness.
        for m in (2,4,8,16):
            words=[]
            for r in range(m):
                words.append(tuple((r+t)-lattice_round(r+t,m,'rdn')==0
                                   for t in range(m)))
            self.assertEqual(len(set(words)),m)
        # Nearest two-addition contexts distinguish twice the spacing.
        for row in signatures():
            self.assertEqual(row['two_gate_classes'],row['phases'])

    def test_depth_independent_source_phase(self):
        ops=[(2,'rne',1),(4,'rup',3),(8,'rdn',5),(16,'rtz',7)]*8
        B=max(2*m if mode=='rne' and m>1 else m for m,mode,_ in ops)
        def loss(x):
            exact=x;y=x
            for m,mode,c in ops:
                exact+=c;y=lattice_round(y+c,m,mode,False)
            return exact-y
        for r in range(B):
            base=loss(10*B+r)
            for shift in (-2*B,-B,B,2*B):
                self.assertEqual(loss(10*B+r+shift),base)

if __name__=='__main__':unittest.main()
