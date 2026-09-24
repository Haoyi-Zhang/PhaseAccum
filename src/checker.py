#!/usr/bin/env python3
"""Self-contained finite certificate checker using exact neighboring values.

This file deliberately imports no producer, phase engine, or local module.
A successful check proves the stated finite input relation, not a mechanized
proof for arbitrary precision or arbitrary networks. Use the article for those
mathematical statements and their assumptions.
"""
from __future__ import annotations
import argparse
from bisect import bisect_left
from fractions import Fraction as Q
import itertools
import json
import math
from pathlib import Path
import re

COUNTS={'round_calls':0,'concrete_rows':0,'concrete_gate_checks':0}

def require(test, message):
    if not test: raise ValueError(message)

def power(e): return Q(1<<e) if e>=0 else Q(1,1<<-e)

def fmt_ok(f):
    require(isinstance(f,dict) and set(f)=={'p','emin','emax'},'format fields')
    require(all(type(v) is int for v in f.values()),'format parameter type')
    require(2<=f['p']<=64 and -2048<=f['emin']<=f['emax']<=2048,'format limits')

def maxfinite(f): return ((1<<f['p'])-1)*power(f['emax']-f['p']+1)

def positive_neighbors(x, f):
    """Locate neighbors from candidate representable values in nearby binades.

Unlike the producer this never rounds a significand with remainder/quotient
logic: candidate values are ordered, then compared to the exact argument.
"""
    p,emin,emax=f['p'],f['emin'],f['emax']
    if x==0:return Q(0),Q(0)
    require(0<x<=maxfinite(f),'outside finite numerical envelope')
    exponent=x.numerator.bit_length()-x.denominator.bit_length()
    # The bit-length estimate differs from floor(log2(x)) by at most one.
    exponents={emin,emax}
    exponents.update(e for e in range(exponent-2,exponent+2) if emin<=e<=emax)
    candidates={Q(0),maxfinite(f)}
    for e in exponents:
        spacing=power(e-p+1)
        ratio=x/spacing
        n=ratio.numerator//ratio.denominator
        lower=0 if e==emin else 1<<(p-1)
        upper=(1<<p)-1
        for k in (n-1,n,n+1,n+2,lower,upper):
            if lower<=k<=upper:candidates.add(k*spacing)
    ordered=sorted(candidates)
    j=bisect_left(ordered,x)
    require(j<len(ordered),'missing upper neighbor')
    if ordered[j]==x:return x,x
    require(j>0,'missing lower neighbor')
    return ordered[j-1],ordered[j]

def round_value(x,f,mode='rne'):
    COUNTS['round_calls']+=1
    require(mode in ('rne','rup','rdn','rtz'),'rounding mode')
    if x<0:
        opposite={'rup':'rdn','rdn':'rup','rne':'rne','rtz':'rtz'}[mode]
        return -round_value(-x,f,opposite)
    low,high=positive_neighbors(x,f)
    if low==high:return low
    if mode in ('rdn','rtz'):return low
    if mode=='rup':return high
    if x-low<high-x:return low
    if high-x<x-low:return high
    # In an adjacent tie, the even endpoint has even index on the gap lattice.
    index=low/(high-low)
    require(index.denominator==1,'neighbor lattice')
    return low if index.numerator%2==0 else high

def explicit_values(f):
    """Small-format oracle used by tests; never instantiated for IEEE formats."""
    require(f['p']<=6 and f['emax']-f['emin']<=32,'explicit oracle cap')
    vals={Q(0)}
    for k in range(1,1<<(f['p']-1)): vals.add(k*power(f['emin']-f['p']+1))
    for e in range(f['emin'],f['emax']+1):
        for k in range(1<<(f['p']-1),1<<f['p']): vals.add(k*power(e-f['p']+1))
    return sorted(vals|{-v for v in vals})

def explicit_round(x,vals,mode):
    j=bisect_left(vals,x)
    if j<len(vals) and vals[j]==x:return x
    require(0<j<len(vals),'explicit envelope')
    a,b=vals[j-1],vals[j]
    if mode=='rdn':return a
    if mode=='rup':return b
    if mode=='rtz':return a if x>0 else b
    if x-a<b-x:return a
    if b-x<x-a:return b
    return a if (a/(b-a)).numerator%2==0 else b

def int_ok(v):
    require(type(v) is int and abs(v).bit_length()<=8192,'bounded integer required')

def case_rows(case):
    if 'relation' in case:return (tuple(r) for r in case['relation'])
    return itertools.product(*(i['values'] for i in case['inputs']))

def prepare(case):
    req={'id','delta_exp','inputs','gates','outputs','cuts'}
    require(isinstance(case,dict) and req<=set(case) and not set(case)-req-{'relation'},'network fields')
    require(isinstance(case['id'],str) and re.fullmatch('[a-z0-9-]{1,80}',case['id']),'identifier')
    int_ok(case['delta_exp']);require(-2048<=case['delta_exp']<=2048,'grid limits')
    delta=power(case['delta_exp'])
    require(1<=len(case['inputs'])<=8 and len(case['gates'])<=64,'dimensions')
    live={};seen=set();depth={};formats=set();max_gate_depth=0
    for inp in case['inputs']:
        require(set(inp)=={'name','format','values'},'input fields')
        name=inp['name']
        require(isinstance(name,str) and re.fullmatch('[a-z][a-z0-9]{0,15}',name) and name not in seen,'input name')
        seen.add(name);depth[name]=0
        fmt_ok(inp['format']);formats.add(tuple(sorted(inp['format'].items())))
        vals=inp['values'];require(1<=len(vals)<=4096 and len(set(vals))==len(vals),'input support')
        for v in vals:
            int_ok(v);require(round_value(v*delta,inp['format'])==v*delta,'input representability')
        live[name]=(min(vals),max(vals))
    if 'relation' in case:
        require(1<=len(case['relation'])<=12000,'relation cap')
        require(len({tuple(r) for r in case['relation']})==len(case['relation']),'duplicate relation')
        for row in case['relation']:
            require(len(row)==len(case['inputs']),'input arity')
            for v,inp in zip(row,case['inputs']):
                int_ok(v);require(v in inp['values'],'relation membership')
        count=len(case['relation'])
    else:
        count=math.prod(len(i['values']) for i in case['inputs'])
        require(count<=12000,'concrete row cap')
    cuts=case['cuts']
    require(cuts==sorted(set(cuts)) and all(type(c) is int and 0<c<len(case['gates']) for c in cuts),'cuts')
    modulus=1;infos=[]
    for g in case['gates']:
        kind=g.get('kind');require(kind in ('add','cast','split','drop'),'kind')
        fields={'kind','args','out'}|({'window'} if kind=='drop' else {'format','mode','cell'})
        if kind=='split':fields.add('residual_format')
        require(set(g)==fields,'gate fields')
        arity=1 if kind in ('cast','drop') else 2
        outputs=0 if kind=='drop' else 2 if kind=='split' else 1
        require(len(g['args'])==arity and len(set(g['args']))==arity and len(g['out'])==outputs,'arity')
        require(all(a in live for a in g['args']),'conservative topology')
        lo=sum(live[a][0] for a in g['args']);hi=sum(live[a][1] for a in g['args'])
        d=1+max(depth[a] for a in g['args']);require(d<=32,'depth')
        max_gate_depth=max(max_gate_depth,d)
        for a in g['args']:del live[a]
        for a in g['out']:
            require(isinstance(a,str) and re.fullmatch('[a-z][a-z0-9]{0,15}',a) and a not in seen,'fresh wire')
            seen.add(a);depth[a]=d
        if kind=='drop':
            require(len(g['window'])==2,'window arity')
            a,b=g['window'];int_ok(a);int_ok(b)
            require(a<=lo<=hi<=b,'drop enclosure')
            modulus=max(modulus,1<<(b-a).bit_length())
            infos.append({'kind':kind,'lo':lo,'hi':hi,'window':[a,b]})
            continue
        f=g['format'];fmt_ok(f);formats.add(tuple(sorted(f.items())))
        mode=g['mode'];require(mode in ('rne','rup','rdn','rtz'),'mode')
        cell=g['cell']
        if cell.get('kind')=='normal':
            require(set(cell)=={'kind','exponent','sign'},'normal cell fields')
            e,sgn=cell['exponent'],cell['sign'];int_ok(e);int_ok(sgn)
            require(f['emin']<=e<=f['emax'] and sgn in (-1,1),'normal cell bounds')
            a,b=power(e),min(power(e+1),maxfinite(f))
            a,b=(a,b) if sgn==1 else (-b,-a)
            spacing=power(e-f['p']+1)
        else:
            require(cell=={'kind':'subnormal'},'subnormal cell fields')
            a,b=-power(f['emin']),power(f['emin']);spacing=power(f['emin']-f['p']+1)
        require(a<=lo*delta<=hi*delta<=b,'rounding cell enclosure')
        require(not(mode=='rtz' and lo<0<hi),'RTZ sign split needed')
        scale=spacing/delta
        require(scale.denominator==1 and scale>=1,'integer rounding spacing')
        m=int(scale);period=m*2 if mode=='rne' and m>1 else m
        modulus=max(modulus,period)
        outlo=round_value(lo*delta,f,mode)/delta;outhi=round_value(hi*delta,f,mode)/delta
        require(outlo.denominator==outhi.denominator==1,'output lattice')
        live[g['out'][0]]=(int(outlo),int(outhi))
        rec={'kind':kind,'lo':lo,'hi':hi,'step_units':m,'negative':hi<=0,'period_units':period,
             'output_interval':[int(outlo),int(outhi)]}
        if kind=='split':
            rf=g['residual_format'];fmt_ok(rf);formats.add(tuple(sorted(rf.items())))
            if m==1: bounds=(0,0)
            elif mode=='rne': bounds=(-(m//2),m//2)
            elif mode=='rup' or (mode=='rtz' and hi<=0):bounds=(1-m,0)
            else:bounds=(0,m-1)
            live[g['out'][1]]=bounds;rec['residual_interval']=list(bounds)
        infos.append(rec)
    require(len(formats)<=8 and len(case['outputs'])==len(live) and set(case['outputs'])==set(live),'live output set')
    require(modulus.bit_length()<=8192,'modulus width')
    return {'modulus_units':modulus,'input_rows':count,'gate_info':infos,'output_intervals':live,
            'max_depth':max_gate_depth,'formats':len(formats)}

def normalize(x):
    # JSON represents tuples as arrays; normalize only containers, never numbers.
    return json.loads(json.dumps(x,sort_keys=True))

def strict_equal(a,b):
    """Avoid Python's True == 1 and 1.0 == 1 at a typed certificate boundary."""
    return json.dumps(a,sort_keys=True,separators=(',',':')) == json.dumps(b,sort_keys=True,separators=(',',':'))

def check(case,cert):
    require(set(cert)=={'network','meta','blocks','rows','max_abs_loss_units','tight_power_two_exponent'},'certificate fields')
    require(strict_equal(cert['network'],case),'certificate is not bound to supplied network')
    meta=prepare(case);require(strict_equal(meta,cert['meta']),'range or format metadata mismatch')
    delta=power(case['delta_exp']);mod=meta['modulus_units']
    boundaries=[0]+case['cuts']+[len(case['gates'])]
    require(len(cert['blocks'])==len(boundaries)-1,'block count')
    source_names=[i['name'] for i in case['inputs']]
    observed={}; block_maps=[{} for _ in cert['blocks']]
    block_names=[None for _ in cert['blocks']]
    for inputs in case_rows(case):
        COUNTS['concrete_rows']+=1
        state={n:v*delta for n,v in zip(source_names,inputs)};start_sum=sum(state.values(),Q(0));loss=Q(0)
        for bi,(begin,end) in enumerate(zip(boundaries,boundaries[1:])):
            in_names=sorted(state);key=tuple(int(state[n]/delta)%mod for n in in_names);before=loss
            for gi in range(begin,end):
                COUNTS['concrete_gate_checks']+=1
                g=case['gates'][gi];t=sum((state.pop(n) for n in g['args']),Q(0))
                inf=meta['gate_info'][gi]
                require(inf['lo']*delta<=t<=inf['hi']*delta,'runtime outside proved range')
                if g['kind']=='drop':loss+=t;continue
                y=round_value(t,g['format'],g['mode']);rho=t-y
                require((y/delta).denominator==1 and (rho/delta).denominator==1,'grid closure')
                state[g['out'][0]]=y
                if g['kind']=='split':
                    require(round_value(rho,g['residual_format'])==rho,'unrepresentable split residual')
                    state[g['out'][1]]=rho
                else:loss+=rho
            out_names=sorted(state)
            val=(tuple(int(state[n]/delta)%mod for n in out_names),int((loss-before)/delta))
            if key in block_maps[bi]:require(block_maps[bi][key]==val,'same phase has different block semantics')
            block_maps[bi][key]=val;block_names[bi]=(in_names,out_names)
        require(start_sum-sum(state.values(),Q(0))==loss,'conservation mismatch')
        key=tuple(v%mod for v in inputs)
        val=(tuple(int(state[n]/delta)%mod for n in case['outputs']),int(loss/delta))
        if key in observed:require(observed[key]==val,'phase quotient is not exact on input relation')
        observed[key]=val
    require(len(observed)<=12000,'phase row cap')
    expected_rows=[{'in':list(k),'out':list(v[0]),'loss':v[1]} for k,v in sorted(observed.items())]
    require(strict_equal(cert['rows'],expected_rows),'incomplete or inaccurate global phase table')
    for bi,b in enumerate(cert['blocks']):
        expected={'begin':boundaries[bi],'end':boundaries[bi+1],
                  'in_names':block_names[bi][0],'out_names':block_names[bi][1],
                  'rows':[{'in':list(k),'out':list(v[0]),'loss':v[1]} for k,v in sorted(block_maps[bi].items())]}
        require(strict_equal(b,expected),'incomplete or inaccurate block relation')
    maximum=max(abs(v[1]) for v in observed.values())
    require(type(cert['max_abs_loss_units']) is int and cert['max_abs_loss_units']==maximum,'tight absolute error')
    bit=None if maximum==0 else (maximum-1).bit_length()+case['delta_exp']
    require(strict_equal(cert['tight_power_two_exponent'],bit),'nearest-bit envelope')
    return {'id':case['id'],'input_rows':meta['input_rows'],'phase_rows':len(observed),
            'block_rows':sum(len(b['rows']) for b in cert['blocks']),
            'gates':len(case['gates']),'max_depth':meta['max_depth'],'formats':meta['formats'],
            'modulus_bits':(mod-1).bit_length(),'max_abs_loss_units':maximum,
            'tight_power_two_exponent':bit,'status':'checked'}

def unique_object(pairs):
    out={}
    for key,value in pairs:
        require(key not in out,'duplicate JSON object key')
        out[key]=value
    return out

def bad_constant(value):
    raise ValueError('nonfinite JSON constant')

def load(path):
    p=Path(path);require(p.stat().st_size<=32*1024*1024,'JSON byte cap')
    return json.loads(p.read_text(),object_pairs_hook=unique_object,parse_constant=bad_constant)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite',required=True);parser.add_argument('--certificates',required=True)
    args=parser.parse_args();suite=load(args.suite);certs=load(args.certificates)
    require(isinstance(suite,list) and 1<=len(suite)<=2000 and isinstance(certs,list) and len(certs)==len(suite),'suite cardinality')
    identifiers=[case.get('id') if isinstance(case,dict) else None for case in suite]
    require(len(identifiers)==len(set(identifiers)),'duplicate suite identifier')
    rows=[check(c,p) for c,p in zip(suite,certs)]
    print(json.dumps({'status':'checked','cases':len(rows),'counts':COUNTS,'rows':rows},indent=2))

if __name__=='__main__':
    try:main()
    except (ValueError,TypeError,KeyError,IndexError,OverflowError) as exc:
        raise SystemExit('CHECK FAILED: '+str(exc))
