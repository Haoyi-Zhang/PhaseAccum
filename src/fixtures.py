"""Deterministic mathematical inputs; no external datasets or runtime sampling."""
from __future__ import annotations
from copy import deepcopy
from itertools import product


def ensure(condition, message):
    if not condition:
        raise ValueError(message)


def fmt(p,emin=-10,emax=10): return {'p':p,'emin':emin,'emax':emax}
def inp(name,values,f=None): return {'name':name,'format':f or fmt(8),'values':list(values)}
def normal(e,sign=1):return {'kind':'normal','exponent':e,'sign':sign}
def add(a,b,out,p=4,mode='rne',e=3,sign=1):
    return {'kind':'add','args':[a,b],'out':[out],'format':fmt(p),'mode':mode,'cell':normal(e,sign)}
def split(a,b,out,residual,p=4,mode='rne',e=3,sign=1,residual_p=8):
    return {'kind':'split','args':[a,b],'out':[out,residual],'format':fmt(p),'mode':mode,
            'cell':normal(e,sign),'residual_format':fmt(residual_p)}
def chain(identifier,x,c0,c1,p0=4,p1=4,m0='rne',m1='rne',sign=1):
    return {'id':identifier,'delta_exp':-4,'inputs':[inp('x',x),inp('c',[c0]),inp('d',[c1])],
            'gates':[add('x','c','s',p0,m0,sign=sign),add('s','d','z',p1,m1,sign=sign)],
            'outputs':['z'],'cuts':[1]}


def deep_split_chain(identifier,length,sign=1,offset=0):
    """Repeated exact-residual interfaces followed by one rounded recomposition.

    The exact total remains in one certified normal cell while formats and modes
    change at every layer.  This exercises composition depth without duplicating
    or inventing inputs.
    """
    if not 2 <= length <= 32:
        raise ValueError('deep chain length')
    modes=('rne','rup','rdn','rtz'); precisions=(7,8,6,8)
    # The total starts well inside [8,16].  Conservative interval propagation
    # may forget the exact q+r correlation at each split; the margin covers
    # the resulting bounded widening through all 32 layers.
    xs=range(176,208) if sign==1 else range(-207,-175)
    c=7 if sign==1 else -7
    gates=[];left='x';right='c'
    for i in range(length-1):
        out=f's{i}';residual=f'r{i}'
        gates.append(split(left,right,out,residual,precisions[(i+offset)%len(precisions)],
                           modes[(i+offset)%len(modes)],sign=sign))
        left,right=out,residual
    gates.append(add(left,right,'z',precisions[(length-1+offset)%len(precisions)],
                     modes[(length-1+offset)%len(modes)],sign=sign))
    return {'id':identifier,'delta_exp':-4,'inputs':[inp('x',xs),inp('c',[c])],
            'gates':gates,'outputs':['z'],'cuts':list(range(4,length,4))}


def serial_add_chain(identifier,sign=1,offset=0):
    """Seven dependent additions over all eight available input ports."""
    modes=('rne','rup','rdn','rtz');precisions=(4,5,6,4,5,6,4)
    xs=range(128,160) if sign==1 else range(-159,-127)
    c=3 if sign==1 else -3
    inputs=[inp('x',xs)]+[inp(f'a{i}',[c]) for i in range(7)]
    gates=[];live='x'
    for i,p in enumerate(precisions):
        out='z' if i==len(precisions)-1 else f't{i}'
        gates.append(add(live,f'a{i}',out,p,modes[(i+offset)%len(modes)],sign=sign))
        live=out
    return {'id':identifier,'delta_exp':-4,'inputs':inputs,'gates':gates,
            'outputs':['z'],'cuts':[2,4,6]}


def balanced_tree(identifier,sign=1,offset=0):
    """A seven-gate balanced reduction tree with eight varying leaves."""
    modes=('rne','rup','rdn','rtz')
    values=[16,17] if sign==1 else [-17,-16]
    names=list('abcdefgh')
    inputs=[inp(n,values) for n in names]
    gates=[]
    specs=[('a','b','u0',4,1),('c','d','u1',5,1),('e','f','u2',4,1),('g','h','u3',5,1),
           ('u0','u1','v0',4,2),('u2','u3','v1',5,2),('v0','v1','z',4,3)]
    for i,(a,b,out,p,e) in enumerate(specs):
        gates.append(add(a,b,out,p,modes[(i+offset)%len(modes)],e=e,sign=sign))
    return {'id':identifier,'delta_exp':-4,'inputs':inputs,'gates':gates,
            'outputs':['z'],'cuts':[4,6]}


def tiny_network_census():
    """Complete two-gate/three-input census used by the finite study.

    The family contains every unordered first-pair topology on three named
    inputs, every ordered pair of the four rounding modes, every ordered pair
    of precisions in {3,4,5}, and both fixed signs.  Each input has two exact
    source values, so all eight source tuples are replayed for every network.
    The chosen supports keep both exact gate arguments inside one declared
    normal cell (exponent 1) for every member of the family.
    """
    modes=('rne','rup','rdn','rtz')
    pairings=(('a','b','c','ab'),('a','c','b','ac'),('b','c','a','bc'))
    positive={'a':[16,17],'b':[18,19],'c':[20,21]}
    cases=[]
    for sign in (1,-1):
        supports=positive if sign==1 else {k:[-v for v in reversed(vals)]
                                           for k,vals in positive.items()}
        sign_name='pos' if sign==1 else 'neg'
        for left,right,tail,topology in pairings:
            for p0,p1,m0,m1 in product((3,4,5),(3,4,5),modes,modes):
                identifier=f'census-{sign_name}-{topology}-p{p0}{p1}-{m0}-{m1}'
                cases.append({
                    'id':identifier,
                    'delta_exp':-4,
                    'inputs':[inp(name,supports[name]) for name in ('a','b','c')],
                    'gates':[add(left,right,'s',p0,m0,e=1,sign=sign),
                             add('s',tail,'z',p1,m1,e=1,sign=sign)],
                    'outputs':['z'],
                    'cuts':[1],
                })
    ensure(len(cases)==2*3*3*3*4*4, 'tiny census cardinality')
    return cases


def structural_challenge_suite():
    """Deterministic three-gate challenge family outside the primary census.

    This is not described as a blind statistical holdout.  It deliberately
    changes input arity, tree shape, depth, cell regime, precision schedule,
    and mode schedule relative to the two-gate census.  Every source support
    is exhausted, so each network replays all 2**4 concrete tuples.
    """
    # Five ordered full binary-tree shapes over a,b,c,d.  Each tuple is the
    # three (left,right,out) additions in topological order.
    topologies={
        'left': [('a','b','u'),('u','c','v'),('v','d','z')],
        'midleft': [('b','c','u'),('a','u','v'),('v','d','z')],
        'midright': [('b','c','u'),('u','d','v'),('a','v','z')],
        'right': [('c','d','u'),('b','u','v'),('a','v','z')],
        'balanced': [('a','b','u'),('c','d','v'),('u','v','z')],
    }
    mode_schedules=(
        ('rne','rne','rne'),('rup','rup','rup'),
        ('rdn','rdn','rdn'),('rtz','rtz','rtz'),
        ('rne','rup','rdn'),('rup','rdn','rtz'),
        ('rdn','rtz','rne'),('rtz','rne','rup'),
    )
    precision_schedules=((3,5,4),(5,3,4))
    cases=[]
    for regime in ('normal','subnormal'):
        if regime=='normal':
            delta_exp=-4
            source_format=fmt(8,-10,10)
            positive=[16,17]
            cells=[normal(1),normal(1),normal(2)]
            target_format=lambda p: fmt(p,-10,10)
        else:
            delta_exp=-6
            source_format=fmt(8,-2,4)
            positive=[1,2]
            cells=[{'kind':'subnormal'} for _ in range(3)]
            target_format=lambda p: fmt(p,-2,4)
        for sign in (1,-1):
            support=positive if sign==1 else [-v for v in reversed(positive)]
            sign_name='pos' if sign==1 else 'neg'
            if regime=='normal':
                gate_cells=[normal(c['exponent'],sign) for c in cells]
            else:
                gate_cells=[dict(c) for c in cells]
            for topology,specs in topologies.items():
                for precisions in precision_schedules:
                    for modes in mode_schedules:
                        mode_tag=''.join({'rne':'n','rup':'u','rdn':'d','rtz':'z'}[m] for m in modes)
                        identifier=(f'challenge-{regime}-{sign_name}-{topology}-'
                                    f'p{precisions[0]}{precisions[1]}{precisions[2]}-{mode_tag}')
                        gates=[]
                        for index,(left,right,out) in enumerate(specs):
                            gates.append({
                                'kind':'add','args':[left,right],'out':[out],
                                'format':target_format(precisions[index]),
                                'mode':modes[index],
                                'cell':gate_cells[index],
                            })
                        cases.append({
                            'id':identifier,'delta_exp':delta_exp,
                            'inputs':[inp(name,support,source_format) for name in ('a','b','c','d')],
                            'gates':gates,'outputs':['z'],'cuts':[1,2],
                        })
    expected=5*2*2*2*8
    ensure(len(cases)==expected, 'structural challenge cardinality')
    ensure(len({c['id'] for c in cases})==expected, 'structural challenge identifiers')
    return cases


def suite():
    cases=[];modes=('rne','rup','rdn','rtz')
    for m0,m1 in product(modes,repeat=2):
        cases.append(chain('positive-'+m0+'-'+m1,range(128,160),7,8,m0=m0,m1=m1))
        cases.append(chain('negative-'+m0+'-'+m1,range(-159,-127),-7,-8,m0=m0,m1=m1,sign=-1))
        cases.append(chain('finer-tail-'+m0+'-'+m1,range(128,160),7,4,p1=5,m0=m0,m1=m1))
        cases.append(chain('coarser-tail-'+m0+'-'+m1,range(128,160),3,8,p0=5,m0=m0,m1=m1))
    cases.append(chain('phase-loss-correlation',[156,180],0,8))
    for m0,m1 in [('rne','rne'),('rup','rdn')]:
        cases.append({'id':'box-'+m0+'-'+m1,'delta_exp':-2,
          'inputs':[inp('x',range(128,192)),inp('y',range(128,192)),inp('c',[4])],
          'gates':[add('x','y','s',6,m0,e=6),add('s','c','z',6,m1,e=6)],'outputs':['z'],'cuts':[1]})
    base_split={'kind':'split','args':['x','c'],'out':['s','r'],'format':fmt(4),'mode':'rne',
           'cell':normal(3),'residual_format':fmt(8)}
    for mode in modes:
        cases.append({'id':'split-subnormal-'+mode,'delta_exp':-4,
          'inputs':[inp('x',range(144,160)),inp('c',[7])],
          'gates':[deepcopy(base_split),{'kind':'cast','args':['r'],'out':['t'],'format':fmt(3,0,10),
                 'mode':mode,'cell':{'kind':'subnormal'}},add('s','t','z',5)],'outputs':['z'],'cuts':[1,2]})
    # RTZ across zero requires separate sign guards and is deliberately rejected.
    cases=[c for c in cases if c['id']!='split-subnormal-rtz']
    cases.append({'id':'split-drain','delta_exp':-4,'inputs':[inp('x',range(144,160)),inp('c',[7])],
                  'gates':[deepcopy(base_split),{'kind':'drop','args':['r'],'out':[],'window':[-8,8]}],
                  'outputs':['s'],'cuts':[1]})
    for correlated in (True,False):
        case={'id':'correlated-inputs' if correlated else 'marginal-inputs','delta_exp':-4,
              'inputs':[inp('x',range(160,176)),inp('y',range(145,161)),inp('c',[16])],
              'gates':[add('x','y','s',4,e=4),add('s','c','z',4,e=4)],'outputs':['z'],'cuts':[1]}
        if correlated:case['relation']=[[x,320-x,16] for x in range(160,176)]
        cases.append(case)
    cases.append({'id':'ordinary-drain','delta_exp':-4,'inputs':[inp('x',range(128,160))],
                  'gates':[{'kind':'drop','args':['x'],'out':[],'window':[128,159]}],'outputs':[],'cuts':[]})
    std=[('binary32-binary16',fmt(24,-126,127),fmt(11,-14,15)),
         ('binary64-binary32',fmt(53,-1022,1023),fmt(24,-126,127)),
         ('binary32-bfloat16',fmt(24,-126,127),fmt(8,-126,127)),
         ('binary64-binary16',fmt(53,-1022,1023),fmt(11,-14,15)),
         ('toy8-toy4',fmt(8),fmt(4))]
    for name,source,target in std:
        p,q=source['p'],target['p'];d=1<<(p-1);m=1<<(p-q)
        g0=add('x','c','s',q,e=0);g1=add('s','d','z',q,e=0)
        g0['format']=target;g1['format']=target
        cases.append({'id':'witness-'+name,'delta_exp':1-p,
             'inputs':[inp('x',[d+2*m+1,d+3*m+1],source),inp('c',[m//2-1],source),inp('d',[m//2],source)],
             'gates':[g0,g1],'outputs':['z'],'cuts':[1]})

    # Depth and topology coverage beyond the two- and three-gate witnesses.
    for offset,length in enumerate((8,16,24,32)):
        cases.append(deep_split_chain(f'deep-split-positive-{length:02d}',length,1,offset))
        cases.append(deep_split_chain(f'deep-split-negative-{length:02d}',length,-1,offset))
    for offset in range(4):
        cases.append(serial_add_chain(f'serial-positive-{offset}',1,offset))
        cases.append(serial_add_chain(f'serial-negative-{offset}',-1,offset))
    for offset in range(3):
        cases.append(balanced_tree(f'balanced-positive-{offset}',1,offset))
        cases.append(balanced_tree(f'balanced-negative-{offset}',-1,offset))
    cases.extend(tiny_network_census())
    cases.extend(structural_challenge_suite())
    return cases


def unsupported_suite():
    bad=[]
    boundary=chain('boundary-crossing',[127,129],0,8);bad.append(boundary)
    rtz={'id':'rtz-sign-crossing','delta_exp':-4,'inputs':[inp('x',[-1,0,1])],
         'gates':[{'kind':'cast','args':['x'],'out':['z'],'format':fmt(3,0,10),'mode':'rtz','cell':{'kind':'subnormal'}}],
         'outputs':['z'],'cuts':[]};bad.append(rtz)
    over=chain('overflow-envelope',[240],16,0)
    over['gates'][0]['format']=fmt(4,-10,3);bad.append(over)
    duplicate=chain('duplicate-wire',[128],7,8);duplicate['gates'][0]['args']=['x','x'];bad.append(duplicate)
    residual=deepcopy(next(c for c in suite() if c['id']=='split-drain'))
    residual['id']='residual-not-representable';residual['gates'][0]['residual_format']=fmt(2,0,10);bad.append(residual)
    return bad
