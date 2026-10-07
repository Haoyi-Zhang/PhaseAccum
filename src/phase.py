"""Producer for guarded residual-phase contracts on conservative DAGs."""
from __future__ import annotations
import itertools
import math
import re
from fractions import Fraction
from .semantics import Format, MODES, two, lattice_round, ceil_error_bit

MAX_INPUT_ROWS = 12000
MAX_PHASE_ROWS = 12000
MAX_GATES = 64
MAX_DEPTH = 32


def integer(x, what='integer'):
    if type(x) is not int or abs(x).bit_length() > 8192:
        raise ValueError(what)
    return x


def validate(case: dict) -> tuple[dict, list, int]:
    required = {'id','delta_exp','inputs','gates','outputs','cuts'}
    if not required <= set(case) or set(case)-required-{'relation'}:
        raise ValueError('network fields')
    if not isinstance(case['id'], str) or not re.fullmatch(r'[a-z0-9-]{1,80}',case['id']):
        raise ValueError('case identifier')
    de=integer(case['delta_exp'])
    if not -2048<=de<=2048: raise ValueError('grid exponent')
    delta=two(de)
    if not 1<=len(case['inputs'])<=8 or not 0<=len(case['gates'])<=MAX_GATES:
        raise ValueError('network dimensions')
    live={}; depth={}; seen=set(); fmt_set=set()
    for inp in case['inputs']:
        if set(inp)!={'name','format','values'}: raise ValueError('input fields')
        name=inp['name']
        if not isinstance(name,str) or not re.fullmatch(r'[a-z][a-z0-9]{0,15}',name) or name in seen:
            raise ValueError('wire name')
        seen.add(name); depth[name]=0
        f=Format.read(inp['format']); fmt_set.add(f)
        vals=inp['values']
        if not 1<=len(vals)<=4096 or len(set(vals))!=len(vals): raise ValueError('input support')
        for v in vals:
            integer(v)
            if not f.represents(v*delta): raise ValueError('input representability')
        live[name]=(min(vals),max(vals))
    if 'relation' in case:
        rows=case['relation']
        if not 1<=len(rows)<=MAX_INPUT_ROWS: raise ValueError('relation size')
        if len({tuple(r) for r in rows})!=len(rows): raise ValueError('duplicate input row')
        for row in rows:
            if len(row)!=len(case['inputs']): raise ValueError('relation arity')
            for v,inp in zip(row,case['inputs']):
                integer(v)
                if v not in inp['values']: raise ValueError('relation support')
        input_count=len(rows)
    else:
        input_count=math.prod(len(x['values']) for x in case['inputs'])
        if input_count>MAX_INPUT_ROWS: raise ValueError('concrete replay cap')
    info=[]; modulus=1; max_gate_depth=0
    for g in case['gates']:
        kind=g.get('kind')
        if kind not in ('add','cast','split','drop'): raise ValueError('gate kind')
        base={'kind','args','out'}
        fields=base|({'window'} if kind=='drop' else {'format','mode','cell'})
        if kind=='split': fields|={'residual_format'}
        if set(g)!=fields: raise ValueError('gate fields')
        arity=1 if kind in ('cast','drop') else 2
        out_arity=0 if kind=='drop' else 2 if kind=='split' else 1
        if len(g['args'])!=arity or len(set(g['args']))!=arity or len(g['out'])!=out_arity:
            raise ValueError('gate arity or duplicate consumption')
        if not all(x in live for x in g['args']): raise ValueError('nonconservative topology')
        d=1+max(depth[x] for x in g['args'])
        if d>MAX_DEPTH: raise ValueError('depth cap')
        max_gate_depth=max(max_gate_depth,d)
        lo=sum(live[x][0] for x in g['args']); hi=sum(live[x][1] for x in g['args'])
        for x in g['args']: del live[x]
        for x in g['out']:
            if not isinstance(x,str) or not re.fullmatch(r'[a-z][a-z0-9]{0,15}',x) or x in seen:
                raise ValueError('fresh output name')
            seen.add(x);depth[x]=d
        if kind=='drop':
            win=g['window']
            if len(win)!=2: raise ValueError('drop interval')
            a,b=map(integer,win)
            if not a<=lo<=hi<=b: raise ValueError('drop enclosure')
            modulus=max(modulus,1<<(b-a).bit_length())
            info.append({'kind':kind,'lo':lo,'hi':hi,'window':win})
            continue
        f=Format.read(g['format']);fmt_set.add(f)
        mode=g['mode'];cell=g['cell']
        if mode not in MODES: raise ValueError('rounding mode')
        if cell.get('kind')=='normal' and set(cell)=={'kind','exponent','sign'}:
            e=integer(cell['exponent']); sign=integer(cell['sign'])
            if sign not in (-1,1) or not f.emin<=e<=f.emax: raise ValueError('normal cell')
            a=two(e); b=min(two(e+1),f.maximum)
            clo,chi=(a,b) if sign==1 else (-b,-a)
            step=two(e-f.p+1)
        elif cell=={'kind':'subnormal'}:
            clo,chi=-two(f.emin),two(f.emin);step=f.quantum
        else: raise ValueError('cell fields')
        if not clo<=lo*delta<=hi*delta<=chi: raise ValueError('uncertified rounding cell')
        if mode=='rtz' and lo<0<hi: raise ValueError('zero-crossing RTZ cell needs sign split')
        m=step/delta
        if m.denominator!=1 or m<1: raise ValueError('grid is coarser than a gate spacing')
        m=int(m); period=2*m if mode=='rne' and m>1 else m
        modulus=max(modulus,period)
        low=f.round(lo*delta,mode)/delta; high=f.round(hi*delta,mode)/delta
        if low.denominator!=1 or high.denominator!=1: raise ValueError('output grid')
        live[g['out'][0]]=(int(low),int(high))
        rec={'kind':kind,'lo':lo,'hi':hi,'step_units':m,'negative':hi<=0,'period_units':period,
             'output_interval':[int(low),int(high)]}
        if kind=='split':
            rf=Format.read(g['residual_format']);fmt_set.add(rf)
            effective=('rup' if hi<=0 else 'rdn') if mode=='rtz' else mode
            bounds=(-m//2,m//2) if effective=='rne' and m>1 else (0,0) if m==1 else (-(m-1),0) if effective=='rup' else (0,m-1)
            live[g['out'][1]]=bounds;rec['residual_interval']=list(bounds)
        info.append(rec)
    if set(live)!=set(case['outputs']) or len(case['outputs'])!=len(live):
        raise ValueError('all and only live outputs must be observed')
    if len(fmt_set)>8: raise ValueError('format-count cap')
    cuts=case['cuts']
    if cuts!=sorted(set(cuts)) or any(type(c) is not int or not 0<c<len(info) for c in cuts):
        raise ValueError('proper interior cuts required')
    if modulus.bit_length()>8192: raise ValueError('phase width cap')
    meta={'modulus_units':modulus,'input_rows':input_count,'gate_info':info,'output_intervals':live,
          'max_depth':max_gate_depth,'formats':len(fmt_set)}
    return meta,info,modulus


def input_rows(case):
    if 'relation' in case:
        yield from (tuple(r) for r in case['relation'])
    else:
        yield from itertools.product(*(x['values'] for x in case['inputs']))


def phase_inputs(case, modulus):
    if 'relation' in case:
        rows=sorted({tuple(v%modulus for v in r) for r in case['relation']})
    else:
        supports=[sorted({v%modulus for v in x['values']}) for x in case['inputs']]
        if math.prod(map(len,supports))>MAX_PHASE_ROWS: raise ValueError('phase enumeration cap')
        rows=list(itertools.product(*supports))
    return rows


def step(case,g,gi,state,loss,modulus):
    """Standalone transfer retains on-demand validation of split constants."""
    return _step(case,g,gi,state,loss,modulus,None)


def _step(case,g,gi,state,loss,modulus,prepared_split):
    args=[state.pop(a) for a in g['args']]
    if g['kind']=='drop':
        a,b=g['window'];v=a+(args[0]-a)%modulus
        if v>b: raise ValueError('empty residue-window intersection')
        return loss+v
    t=sum(args);m=gi['step_units']
    q=lattice_round(t,m,g['mode'],gi['negative']);rho=t-q
    state[g['out'][0]]=q%modulus
    if g['kind']=='split':
        rf,delta = (Format.read(g['residual_format']),two(case['delta_exp'])) if prepared_split is None else prepared_split
        if not rf.represents(rho*delta): raise ValueError('unrepresentable exact residual')
        state[g['out'][1]]=rho%modulus
    else: loss+=rho
    return loss


def build(case):
    meta,info,modulus=validate(case)
    # Immutable constants belong to this validated build, not a gate-name cache.
    delta=two(case['delta_exp']) if any(g['kind']=='split' for g in case['gates']) else None
    split_constants=tuple((Format.read(g['residual_format']),delta) if g['kind']=='split' else None
                          for g in case['gates'])
    inp=phase_inputs(case,modulus)
    names=[x['name'] for x in case['inputs']]
    boundaries=[0]+case['cuts']+[len(case['gates'])]
    # Keep joint (phase tuple, loss) states; never Cartesianize their marginals.
    relation=[(dict(zip(names,r)),0) for r in inp]
    blocks=[]
    for begin,end in zip(boundaries,boundaries[1:]):
        incoming=sorted(relation[0][0]) if relation else []
        table={};nextrel=[]
        for state,loss in relation:
            key=tuple(state[n] for n in incoming)
            if key not in table:
                s=dict(state);inc=0
                for i in range(begin,end):
                    inc=_step(case,case['gates'][i],info[i],s,inc,modulus,split_constants[i])
                outgoing=sorted(s)
                table[key]=(tuple(s[n] for n in outgoing),inc)
            out,inc=table[key]
            nextrel.append((dict(zip(outgoing,out)),loss+inc))
        blocks.append({'begin':begin,'end':end,'in_names':incoming,'out_names':outgoing,
                       'rows':[{'in':list(k),'out':list(v[0]),'loss':v[1]} for k,v in sorted(table.items())]})
        # Deduplication is on the WHOLE joint state, including its accumulated loss.
        unique={(tuple(sorted(s.items())),d) for s,d in nextrel}
        relation=[(dict(s),d) for s,d in sorted(unique)]
    # Reconstruct source-indexed rows via block composition, not monolithic replay.
    rows=[]
    lookups=[{tuple(r['in']):r for r in b['rows']} for b in blocks]
    for inp_row in inp:
        state=dict(zip(names,inp_row));loss=0
        for b,lookup in zip(blocks,lookups):
            r=lookup[tuple(state[n] for n in b['in_names'])]
            state=dict(zip(b['out_names'],r['out']));loss+=r['loss']
        rows.append({'in':list(inp_row),'out':[state[n] for n in case['outputs']],'loss':loss})
    maximum=max(abs(r['loss']) for r in rows)
    return {'network':case,'meta':meta,'blocks':blocks,'rows':rows,
            'max_abs_loss_units':maximum,'tight_power_two_exponent':ceil_error_bit(maximum,case['delta_exp'])}
