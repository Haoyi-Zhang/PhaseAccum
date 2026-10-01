"""Deterministic, bounded finite validation; no external inputs or solvers."""
from __future__ import annotations
import copy, csv, json, os, resource, time
from pathlib import Path
from fractions import Fraction as Q
from . import checker
from .fixtures import suite, tiny_network_census, structural_challenge_suite, unsupported_suite
from .phase import build
from .semantics import Format, full_residual_alphabet_representable, lattice_round

ROOT=Path(__file__).resolve().parents[1]


def ensure(condition, message):
    if not condition:
        raise RuntimeError(message)


def write(path, obj):
    path.write_text(json.dumps(obj,indent=2,sort_keys=True)+'\n')

def observation_word_bit(r, context, m):
    """Lemma 3.1 / formula (10) on the integer phase grid."""
    n=2*m
    j=(r+context)%n
    return j==0 or m<=j<n


def check_observation_word_formula(words, m, label='observation word'):
    """Check every retained phase/context bit, not only one cyclic base row."""
    n=2*m
    ensure(len(words)==n, f'{label}: phase-row count')
    checks=0
    for r,row in enumerate(words):
        ensure(len(row)==n, f'{label}: context count for r={r}')
        for context,actual in enumerate(row):
            expected=observation_word_bit(r,context,m)
            j=(r+context)%n
            ensure(actual==expected,
                   f'{label}: formula (10) mismatch r={r} t={context} j={j}')
            checks+=1
    return checks


def check_constructive_separators(words, m, label='separator'):
    n=2*m
    checks=0
    for r in range(n):
        for s in range(n):
            if r==s:
                continue
            distance=(s-r)%n
            context=((m-1 if distance<=m else 1)-r)%n
            ensure(not words[r][context] and words[s][context],
                   f'{label}: gap={m.bit_length()-1} r={r} s={s} t={context}')
            checks+=1
    return checks


def signatures():
    grid=checker.explicit_values({'p':4,'emin':-10,'emax':10})
    result=[]
    for gap in range(1,7):
        m=1<<gap;n=2*m
        signatures=[];single=[]
        for r in range(n):
            sig=[];sg=[]
            for c in range(n):
                t=Q(8)+Q(r+c,m)
                y=checker.explicit_round(t,grid,'rne')
                z=checker.explicit_round(y+Q(1,2),grid,'rne')
                sig.append(abs(z-t-Q(1,2))<=Q(1,2));sg.append(int(abs(y-t)*m))
            signatures.append(tuple(sig));single.append(tuple(sg))
        formula_checks=check_observation_word_formula(signatures,m,
                                                       f'observation word gap {gap}')
        two_classes=len(set(signatures));one_classes=len(set(single))
        ensure(two_classes==n, f'two-add class count for gap {gap}')
        ensure(one_classes==m, f'one-add class count for gap {gap}')
        ensure(all(single[r]==single[r+m] for r in range(m)),
               f'one-add periodicity for gap {gap}')
        separator_checks=check_constructive_separators(signatures,m)

        result.append({'gap':gap,'phases':n,'contexts':n,'two_gate_classes':two_classes,
                       'one_gate_absolute_classes':one_classes,'one_gate_class_target':m,
                       'input_context_pairs':n*n,'formula_10_bit_checks':formula_checks,
                       'oracle_gate_evaluations':2*n*n,'separator_checks':separator_checks,
                       'observation_words':[''.join('1' if b else '0' for b in row) for row in signatures],
                       'one_gate_absolute_loss_units':single,
                       'base_observation_word':''.join('1' if x else '0' for x in signatures[0])})
    return result


def observation_word_mutation_regression(signature_rows):
    """A bit flip that evades the former aggregate checks must fail formula (10)."""
    row=next(x for x in signature_rows if x['gap']==3)
    m=1<<row['gap'];n=2*m
    words=[[bit=='1' for bit in word] for word in row['observation_words']]
    r=context=1;j=(r+context)%n
    ensure(words[r][context] is False, 'mutation regression baseline changed')
    words[r][context]=True
    legacy_classes=len({tuple(word) for word in words})
    ensure(legacy_classes==n, 'target mutation no longer preserves the class count')
    legacy_separators=check_constructive_separators(words,m,'mutated legacy separator')
    rejected=False;reason=''
    try:
        check_observation_word_formula(words,m,'mutated observation word')
    except RuntimeError as exc:
        rejected=True;reason=str(exc)
    ensure(rejected, 'formula (10) accepted the targeted bit mutation')
    return {
        'status':'rejected-by-full-formula-check',
        'gap':3,
        'mutation':{'r':r,'context':context,'j':j,'from':0,'to':1},
        'legacy_two_gate_classes_after_mutation':legacy_classes,
        'legacy_separator_checks_after_mutation':legacy_separators,
        'legacy_conditions_still_pass':True,
        'formula_10_expected_bit':int(observation_word_bit(r,context,m)),
        'mutated_bit':1,
        'full_formula_check_rejected':True,
        'rejection_reason':reason,
        'boundary':'Targeted regression for checker sensitivity; not an additional network or theorem proof.'
    }


def rounding_oracle_audit():
    """Compare three exact rounding implementations on all small-format gaps.

    For p=2..5 and a fixed compact exponent range, every adjacent pair of
    finite values contributes its quarter point, midpoint, and three-quarter
    point under all four rounding modes.  This deliberately includes signs,
    binade boundaries, subnormal/normal transitions, and exact midpoint ties.
    """
    rows=[];comparisons=0
    for p in range(2,6):
        fd={'p':p,'emin':-2,'emax':2}
        explicit=checker.explicit_values(fd)
        producer=Format.read(fd)
        probes=0
        for a,b in zip(explicit,explicit[1:]):
            for numerator in (1,2,3):
                x=a+Q(numerator,4)*(b-a)
                for mode in ('rne','rup','rdn','rtz'):
                    reference=checker.explicit_round(x,explicit,mode)
                    ensure(checker.round_value(x,fd,mode)==reference, 'checker rounding oracle disagreement')
                    ensure(producer.round(x,mode)==reference, 'producer rounding oracle disagreement')
                    comparisons+=1;probes+=1
        rows.append({'format':fd,'finite_values':len(explicit),
                     'adjacent_intervals':len(explicit)-1,
                     'mode_point_comparisons':probes})
    ensure(comparisons==4224, 'rounding oracle comparison count')
    return {'formats':len(rows),'comparisons':comparisons,
            'points_per_gap':3,'rounding_modes':4,'rows':rows}


def census_audit(cases, rows):
    """Prove that the retained census exhausts its declared finite axes."""
    census_cases=[c for c in cases if c['id'].startswith('census-')]
    census_rows=[r for r in rows if r['id'].startswith('census-')]
    expected=tiny_network_census()
    ensure(census_cases==expected, 'tiny census generator mismatch')
    ensure(len(census_cases)==864 and len(census_rows)==864, 'tiny census count mismatch')
    dimensions={
        'signs':['negative','positive'],
        'first_pair_topologies':['ab-then-c','ac-then-b','bc-then-a'],
        'target_precisions':[3,4,5],
        'rounding_modes':['rne','rup','rdn','rtz'],
        'source_support_size_per_input':2,
    }
    return {
        'status':'complete-over-declared-finite-axes',
        'definition':('All 3 first-pair topologies, both fixed signs, all ordered '
                      'precision pairs in {3,4,5}^2, all ordered rounding-mode '
                      'pairs in {rne,rup,rdn,rtz}^2, and all 2^3 source tuples.'),
        'dimensions':dimensions,
        'expected_networks':2*3*9*16,
        'networks':len(census_rows),
        'concrete_input_rows':sum(r['input_rows'] for r in census_rows),
        'phase_input_rows':sum(r['phase_rows'] for r in census_rows),
        'block_table_rows':sum(r['block_rows'] for r in census_rows),
        'max_gates':max(r['gates'] for r in census_rows),
        'max_depth':max(r['max_depth'] for r in census_rows),
        'cell_exponent':1,
        'delta_exp':-4,
        'boundary':('A complete census only for this explicitly declared tiny '
                    'family; it is not exhaustive over all bounded networks.'),
    }


def structural_challenge_audit(cases, rows):
    """Check the exact axes of the topology/cell challenge family.

    The family is deliberately disjoint from the primary two-gate census in
    arity and depth.  It is deterministic and exhaustive over its declared
    axes, but it is not described as a blind or population-representative test.
    """
    challenge_cases=[c for c in cases if c['id'].startswith('challenge-')]
    challenge_rows=[r for r in rows if r['id'].startswith('challenge-')]
    expected=structural_challenge_suite()
    ensure(challenge_cases==expected, 'structural challenge generator mismatch')
    ensure(len(challenge_cases)==320 and len(challenge_rows)==320,
           'structural challenge count mismatch')
    return {
        'status':'complete-over-declared-challenge-axes',
        'definition':('All five ordered four-leaf binary-tree shapes, both signs, '
                      'normal and central-subnormal cells, two precision schedules, '
                      'eight mode schedules, and all 2^4 source tuples.'),
        'dimensions':{
            'tree_shapes':['left','midleft','midright','right','balanced'],
            'signs':['negative','positive'],
            'cell_regimes':['normal','subnormal'],
            'precision_schedules':[[3,5,4],[5,3,4]],
            'mode_schedules':8,
            'source_support_size_per_input':2,
        },
        'expected_networks':320,
        'networks':len(challenge_rows),
        'concrete_input_rows':sum(r['input_rows'] for r in challenge_rows),
        'phase_input_rows':sum(r['phase_rows'] for r in challenge_rows),
        'block_table_rows':sum(r['block_rows'] for r in challenge_rows),
        'max_gates':max(r['gates'] for r in challenge_rows),
        'max_depth':max(r['max_depth'] for r in challenge_rows),
        'boundary':('A deterministic structural challenge, not a blind statistical '
                    'holdout and not evidence of real-program representativeness.'),
    }

def mutate(case,cert):
    """Syntactic controls and semantic mutations with freshly valid metadata."""
    pairs=[]
    def item(label,change):
        ca=copy.deepcopy(case);ce=copy.deepcopy(cert)
        change(ca,ce);pairs.append((label,ca,ce))
    item('boolean-in-integer-row',lambda c,s:s['rows'][0].__setitem__('loss',True))
    item('incorrect-tight-bound',lambda c,s:s.__setitem__('max_abs_loss_units',s['max_abs_loss_units']+1))
    item('incorrect-power-envelope',lambda c,s:s.__setitem__('tight_power_two_exponent',s['tight_power_two_exponent']+1))
    item('missing-source-phase',lambda c,s:s['rows'].pop())
    item('missing-block-phase',lambda c,s:s['blocks'][0]['rows'].pop())
    item('duplicate-global-row',lambda c,s:s['rows'].append(copy.deepcopy(s['rows'][0])))
    item('duplicate-block-row',lambda c,s:s['blocks'][0]['rows'].append(copy.deepcopy(s['blocks'][0]['rows'][0])))
    def surplus_global(c,s):
        row=copy.deepcopy(s['rows'][0]);row['in'][0]=(row['in'][0]+1)%s['meta']['modulus_units']
        s['rows'].append(row)
    item('surplus-global-phase',surplus_global)
    def out_of_domain(c,s):
        s['rows'][0]['in'][0]=s['meta']['modulus_units']
    item('out-of-domain-global-phase',out_of_domain)
    item('corrupt-signed-loss',lambda c,s:s['rows'][0].__setitem__('loss',s['rows'][0]['loss']+1))
    item('corrupt-block-output-phase',lambda c,s:s['blocks'][0]['rows'][0]['out'].__setitem__(0,s['blocks'][0]['rows'][0]['out'][0]+1))
    item('corrupt-block-input-name',lambda c,s:s['blocks'][0]['in_names'].__setitem__(0,'bogus'))
    item('corrupt-block-boundary',lambda c,s:s['blocks'][0].__setitem__('end',s['blocks'][0]['end']+1))
    def rounding(c,s):
        c['gates'][0]['mode']='rup' if c['gates'][0]['mode']!='rup' else 'rdn'
        s['network']=copy.deepcopy(c);s['meta']=checker.normalize(checker.prepare(c))
    item('changed-rounding-stale-contract',rounding)
    def cell(c,s):
        c['gates'][0]['cell']['exponent']+=1;s['network']=copy.deepcopy(c)
    item('false-cell-guard',cell)
    def change_format(c,s):
        c['gates'][0]['format']['p']+=1
        s['network']=copy.deepcopy(c);s['meta']=checker.normalize(checker.prepare(c))
    item('changed-format-stale-contract',change_format)
    def valid_topology(c,s):
        c['gates'][0]['args'][1],c['gates'][1]['args'][1]=c['gates'][1]['args'][1],c['gates'][0]['args'][1]
        s['network']=copy.deepcopy(c);s['meta']=checker.normalize(checker.prepare(c))
    item('changed-legal-topology-stale-contract',valid_topology)
    def cuts(c,s):
        c['cuts']=[];s['network']=copy.deepcopy(c);s['meta']=checker.normalize(checker.prepare(c))
    item('changed-cut-partition-stale-contract',cuts)
    def topology(c,s):
        c['gates'][0]['args'][1]=c['gates'][0]['args'][0];s['network']=copy.deepcopy(c)
    item('duplicate-wire-consumption',topology)
    out=[]
    for label,ca,ce in pairs:
        try: checker.check(ca,ce)
        except (ValueError,TypeError,KeyError) as e:
            out.append({'mutation':label,'rejected':True,'reason':str(e)})
        else: raise AssertionError('accepted mutation '+label)
    return out



def composition_cut_invariance(cases):
    """Replay one depth-32 network under four legal block partitions."""
    base=next(c for c in cases if c['id']=='deep-split-positive-32')
    n=len(base['gates'])
    partitions=[
        ('monolithic',[]),
        ('declared',list(base['cuts'])),
        ('every-gate',list(range(1,n))),
        ('irregular',[1,3,7,12,18,25,31]),
    ]
    rows=[];reference=None;bound=None
    for label,cuts in partitions:
        case=copy.deepcopy(base);case['id']='cut-'+label;case['cuts']=cuts
        cert=checker.normalize(build(case));checked=checker.check(case,cert)
        projection={'rows':cert['rows'],'max_abs_loss_units':cert['max_abs_loss_units'],
                    'tight_power_two_exponent':cert['tight_power_two_exponent']}
        if reference is None:
            reference=projection;bound=cert['max_abs_loss_units']
        else:
            ensure(checker.strict_equal(reference,projection), 'cut partition changed global contract')
        rows.append({'partition':label,'cuts':cuts,'blocks':len(cert['blocks']),
                     'source_rows':checked['input_rows'],'phase_rows':checked['phase_rows'],
                     'block_rows':checked['block_rows'],'max_abs_loss_units':bound})
    return {'network_gates':n,'network_depth':32,'partitions_checked':len(rows),
            'source_rows_replayed':sum(r['source_rows'] for r in rows),
            'block_rows_checked':sum(r['block_rows'] for r in rows),
            'identical_global_contract':True,'rows':rows}


def phase_loss_ablation():
    """An exact two-state cut and its Cartesianized phase/loss replacement."""
    target={'p':4,'emin':-10,'emax':10}; delta=Q(1,16)
    cut=[]
    for x in (156,180):
        y=checker.round_value(x*delta,target,'rne')
        rho=x*delta-y
        increment=y+Q(1,2)-checker.round_value(y+Q(1,2),target,'rne')
        cut.append({'input_units':x,'cut_value_units':int(y/delta),
                    'phase_units':int(y/delta)%32,'incoming_loss_units':int(rho/delta),
                    'next_loss_units':int(increment/delta)})
    exact=sorted({r['incoming_loss_units']+r['next_loss_units'] for r in cut})
    product=sorted({r['incoming_loss_units']+s['next_loss_units'] for r in cut for s in cut})
    ensure(exact==[-4,4] and product==[-12,-4,4,12], 'phase/loss ablation mismatch')
    return {'delta_exp':-4,'modulus_units':32,'cut_rows':cut,'exact_final_loss_units':exact,
            'cartesianized_final_loss_units':product,'exact_dyadic_exponent':-2,
            'cartesianized_dyadic_exponent':0,
            'interpretation':'Two-bit inflation from separating the cut phase and signed incoming loss.'}


def residual_alphabets():
    """Check the algebraic representability criterion against an independent oracle."""
    rows=[];checks=0
    for gap in range(1,6):
        m=1<<gap
        for de in (-1,1):
            for p in range(2,7):
                for emin in (-1,1):
                    for emax in (emin,emin+3):
                        f=Format(p,emin,emax);fd={'p':p,'emin':emin,'emax':emax}
                        grid=set(checker.explicit_values(fd))
                        for mode in ('rne','rdn'):
                            ns=range(-m//2,m//2+1) if mode=='rne' else range(m)
                            observed=[n*checker.power(de) in grid for n in ns]
                            checks+=len(observed)
                            expected=full_residual_alphabet_representable(f,gap,de,mode)
                            ensure(expected==all(observed), 'residual alphabet criterion disagreement')
                            rows.append({'gap':gap,'delta_exp':de,'format':fd,'mode':mode,
                                         'criterion':expected,'oracle':all(observed),'residuals':len(observed)})
    return {'format_mode_obligations':len(rows),'residual_membership_checks':checks,'rows':rows}


def residual_periods():
    """Check the claimed least periods with nonredundant witnesses.

    Periodicity is sampled over four complete periods.  Minimality is checked
    for every smaller positive shift using an analytic witness: zero rejects
    shifts not divisible by m, and the nearest-even midpoint rejects shift m.
    The general result remains the paper proof; these are implementation tests.
    """
    rows=[];periodicity=0;minimality=0
    variants=(('rne',False,'nearest-even'),('rup',False,'upward'),
              ('rdn',False,'downward'),('rtz',False,'toward-zero-positive'),
              ('rtz',True,'toward-zero-negative'))
    for m in (1,2,4,8,16,32,64):
        for mode,negative,label in variants:
            period=1 if m==1 else (2*m if mode=='rne' else m)
            def rho(t): return t-lattice_round(t,m,mode,negative)
            for t in range(-2*period,2*period):
                periodicity+=1
                ensure(rho(t)==rho(t+period),
                       f'periodicity m={m} mode={label} t={t}')
            witnesses=[]
            for candidate in range(1,period):
                witness=0 if candidate % m else m//2
                minimality+=1
                ensure(rho(witness)!=rho(witness+candidate),
                       f'minimality m={m} mode={label} shift={candidate}')
                witnesses.append({'shift':candidate,'witness':witness})
            rows.append({'spacing_units':m,'mode':label,'negative_guard':negative,
                         'least_period_units':period,
                         'smaller_shifts_rejected':len(witnesses),
                         'first_witnesses':witnesses[:8]})
    ensure(len(rows)==35, 'residual-period configuration count')
    return {'configurations':len(rows),'periodicity_checks':periodicity,
            'minimality_checks':minimality,'total_checks':periodicity+minimality,
            'window_periods_each_side':2,'rows':rows}


def witnesses(cases,certs):
    out=[]
    for case,cert in zip(cases,certs):
        if not case['id'].startswith('witness-'):continue
        p=case['inputs'][0]['format']['p'];q=case['gates'][0]['format']['p']
        delta=checker.power(case['delta_exp']);records=[]
        for row in checker.case_rows(case):
            x,c,d=(v*delta for v in row)
            first=checker.round_value(x+c,case['gates'][0]['format'])
            second=checker.round_value(first+d,case['gates'][1]['format'])
            bits=format(row[0]-(1<<(p-1)),f'0{p-1}b')
            runs={}
            for name,char in [('zeros','0'),('ones','1')]:
                runs['leading_'+name]=len(bits)-len(bits.lstrip(char))
                runs['trailing_'+name]=len(bits)-len(bits.rstrip(char))
            records.append({'x':str(x),'c':str(c),'d':str(d),'first_sum':str(x+c),
                'first_result':str(first),'second_result':str(second),'exact_sum':str(x+c+d),
                'signed_loss':str(x+c+d-second),'fraction_bits':bits,
                'sign':1,'exponent':0,'run_features':runs})
        ensure(records[0]['run_features']==records[1]['run_features'], 'run-feature witness mismatch')
        ensure(records[0]['signed_loss']!=records[1]['signed_loss'], 'witness failed to separate losses')
        out.append({'id':case['id'],'source_precision':p,'target_precision':q,
                    'phase_state_lower_bound_power':p-q+1,'records':records,
                    'minimality_scope':'Two is the worst-case shortest translated-add context length for absolute-error observations; not generic circuit minimization.'})
    return out


def standard_residual_witnesses(cases):
    """Exact residuals not representable in the coarse target format.

This is a numerical gate-domain check, not a claim about any implementation
of an error-free transformation or about the synthesis of a scalar kernel.
"""
    out=[]
    for case in cases:
        if not case['id'].startswith('witness-binary'): continue
        source=case['inputs'][0]['format']; target=case['gates'][0]['format']
        p=source['p']; q=target['p']; k=p-q
        delta=checker.power(1-p); n=(1<<(k-1))-1
        x=Q(1)+n*delta
        ensure(checker.round_value(x,source)==x, 'standard witness source representability')
        rounded=checker.round_value(x,target)
        residual=x-rounded
        ensure(residual==n*delta, 'standard witness residual value')
        ensure(checker.round_value(residual,target)!=residual, 'standard witness unexpectedly representable')
        out.append({'id':case['id'],'source_format':source,'target_format':target,
                    'input':str(x),'rounded':str(rounded),'residual':str(residual),
                    'residual_significand_bits':k-1,'coarse_target_precision':q,
                    'representable_in_coarse_target':False})
    ensure(len(out)==4, 'standard witness count')
    return out

def main():
    start=time.monotonic();cpu=time.process_time()
    cases=suite();bad=unsupported_suite()
    (ROOT/'inputs').mkdir(exist_ok=True);(ROOT/'results').mkdir(exist_ok=True)
    # Deterministic case data are retained, and regenerated from the generator.
    write(ROOT/'inputs/suite.json',cases);write(ROOT/'inputs/unsupported.json',bad)
    certs=[];rows=[]
    for case in cases:
        t=time.process_time();cert=checker.normalize(build(case));producer=time.process_time()-t
        t=time.process_time();row=checker.check(case,cert);checktime=time.process_time()-t
        row.update({'producer_cpu_seconds':producer,'checker_cpu_seconds':checktime,
                    'delta_exp':case['delta_exp'],
                    'max_abs_error':str(row['max_abs_loss_units']*checker.power(case['delta_exp']))})
        certs.append(cert);rows.append(row)
    base_counts=dict(checker.COUNTS)
    unsupported=[]
    for c in bad:
        try: build(c)
        except (ValueError,TypeError,KeyError) as e:unsupported.append({'id':c['id'],'rejected':True,'reason':str(e)})
        else:raise AssertionError('unsupported accepted '+c['id'])
    # Avoid assuming that a syntax rejection demonstrates semantic strength.
    mutant=mutate(cases[0],certs[0])
    corr=next(i for i,c in enumerate(cases) if c['id']=='correlated-inputs')
    c=copy.deepcopy(cases[corr]);s=copy.deepcopy(certs[corr]);c.pop('relation');s['network']=copy.deepcopy(c);s['meta']=checker.normalize(checker.prepare(c))
    try:checker.check(c,s)
    except ValueError as e:mutant.append({'mutation':'correlation-erased-stale-contract','rejected':True,'reason':str(e)})
    else:raise AssertionError('erased correlation accepted')
    sig=signatures();word_mutation=observation_word_mutation_regression(sig)
    ablation=phase_loss_ablation();alphabets=residual_alphabets()
    rounding=rounding_oracle_audit();census=census_audit(cases,rows)
    challenge=structural_challenge_audit(cases,rows)
    periods=residual_periods()
    cuts=composition_cut_invariance(cases)
    write(ROOT/'results/phase-loss-ablation.json',ablation)
    write(ROOT/'results/residual-alphabets.json',alphabets)
    write(ROOT/'results/residual-periods.json',periods)
    write(ROOT/'results/rounding-oracle.json',rounding)
    write(ROOT/'results/tiny-network-census.json',census)
    write(ROOT/'results/structural-challenge.json',challenge)
    write(ROOT/'results/composition-cuts.json',cuts)
    write(ROOT/'results/counterexamples.json',witnesses(cases,certs))
    write(ROOT/'results/standard-residual-witnesses.json',standard_residual_witnesses(cases))
    write(ROOT/'results/certificates.json',certs)
    write(ROOT/'results/signatures.json',sig)
    write(ROOT/'results/observation-word-mutation.json',word_mutation)
    write(ROOT/'results/mutations.json',mutant)
    write(ROOT/'results/unsupported.json',unsupported)
    with (ROOT/'results/networks.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    summary={'status':'all-finite-checks-passed','networks':len(cases),
             'concrete_input_rows':sum(r['input_rows'] for r in rows),
             'phase_input_rows':sum(r['phase_rows'] for r in rows),
             'block_table_rows':sum(r['block_rows'] for r in rows),
             'max_gates':max(r['gates'] for r in rows),'max_depth':max(r['max_depth'] for r in rows),
             'signature_input_context_pairs':sum(r['input_context_pairs'] for r in sig),
             'observation_word_formula_checks':sum(r['formula_10_bit_checks'] for r in sig),
             'one_gate_class_count_checks':len(sig),
             'observation_word_mutation_rejections':1,
             'constructive_separator_checks':sum(r['separator_checks'] for r in sig),
             'signature_oracle_gate_evaluations':sum(r['oracle_gate_evaluations'] for r in sig),
             'rounding_oracle_formats':rounding['formats'],
             'rounding_oracle_comparisons':rounding['comparisons'],
             'census_networks':census['networks'],
             'census_input_rows':census['concrete_input_rows'],
             'structural_challenge_networks':challenge['networks'],
             'structural_challenge_input_rows':challenge['concrete_input_rows'],
             'residual_alphabet_obligations':alphabets['format_mode_obligations'],
             'residual_membership_checks':alphabets['residual_membership_checks'],
             'residual_period_configurations':periods['configurations'],
             'residual_period_checks':periods['total_checks'],
             'standard_residual_witnesses':4,
             'composition_partitions_checked':cuts['partitions_checked'],
             'composition_source_rows_replayed':cuts['source_rows_replayed'],
             'composition_block_rows_checked':cuts['block_rows_checked'],
             'mutations_rejected':len(mutant),'unsupported_rejected':len(unsupported),
             'independent_oracle_networks':census['networks']+challenge['networks'],
             'independent_oracle_input_rows':census['concrete_input_rows']+challenge['concrete_input_rows'],
             'base_replay_counts':base_counts,'all_replay_counts':checker.COUNTS,
             'wall_seconds':time.monotonic()-start,'cpu_seconds':time.process_time()-cpu,
             'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
             'workers':1,'seeds':'none; deterministic exhaustive families and declared challenge axes',
             'evidence_boundary':'Finite rational-model replay, not a mechanized general proof or hardware benchmark.'}
    summary['bounded_obligations'] = (summary['concrete_input_rows']
         + summary['signature_input_context_pairs'] + summary['constructive_separator_checks']
         + len(mutant) + len(unsupported) + rounding['comparisons'] + alphabets['residual_membership_checks']
         + alphabets['format_mode_obligations'] + 4 + periods['total_checks']
         + cuts['source_rows_replayed'] + cuts['block_rows_checked']
         + summary['independent_oracle_input_rows'])
    ensure(summary['bounded_obligations'] < 100000, 'bounded-obligation cap exceeded')
    write(ROOT/'results/summary.json',summary)
    print(json.dumps(summary,indent=2))

if __name__=='__main__': main()
