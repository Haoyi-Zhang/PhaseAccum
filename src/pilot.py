from fractions import Fraction as F
from bisect import bisect_left
import json,time,resource,os
os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,2*1024**3))
resource.setrlimit(resource.RLIMIT_CPU,(30,30))
start=time.monotonic(); cpu=time.process_time()
def ensure(condition,message):
 if not condition: raise RuntimeError(message)
# Oracle: explicitly ordered finite toy-format values, no lattice-rounding code.
def pow2(e): return F(2**e) if e>=0 else F(1,2**(-e))
def values(p,emin=-10,emax=10):
 out={F(0)}
 for k in range(1,2**(p-1)):out.add(k*pow2(emin-p+1))
 for e in range(emin,emax+1):
  for k in range(2**(p-1),2**p):out.add(k*pow2(e-p+1))
 return sorted(out|{-v for v in out})
grid=values(4)
def rnd(t):
 j=bisect_left(grid,t)
 if j<len(grid) and grid[j]==t:return t
 lo,hi=grid[j-1],grid[j]
 if t-lo<hi-t:return lo
 if t-lo>hi-t:return hi
 # Ties: the even multiple of the local spacing.
 return lo if (lo/(hi-lo)).numerator%2==0 else hi
rows=[]
for gap in range(1,7):
 m=2**gap; n=2*m; delta=F(1,m)
 signatures=[]; one=[]
 for r in range(n):
  signature=[]; single=[]
  for c in range(n):
   t=F(8)+(r+c)*delta
   y=rnd(t); z=rnd(y+F(1,2))
   err=z-(t+F(1,2)); single.append(abs(y-t))
   signature.append(abs(err)<=F(1,2))
  signatures.append(tuple(signature)); one.append(tuple(single))
 ensure(len(set(signatures))==n,'two-gate class count')
 ensure(all(one[i]==one[i+m] for i in range(m)),'one-gate periodicity')
 expected=[r==0 or r>=m for r in range(n)]
 ensure(list(signatures[0])==expected,'observation word')
 rows.append({'gap':gap,'phases':n,'contexts':n,'two_gate_signature_classes':len(set(signatures)), 'single_gate_absolute_classes':len(set(one)), 'oracle_gate_evaluations':2*n*n})
x0=F(161,16); x1=F(177,16); c=F(7,16)
example=[]
for x in [x0,x1]:
 s=rnd(x+c); z=rnd(s+F(1,2))
 example.append({'x':str(x),'c':str(c),'s':str(s),'out':str(z),'signed_error':str(z-x-c-F(1,2))})
out={'status':'passed','worker_count':1,'format_precision':4,'oracle':'enumerated neighboring finite values','phase_rows':rows,'same_run_count_witness':example,'wall_seconds':time.monotonic()-start,'cpu_seconds':time.process_time()-cpu,'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
print(json.dumps(out,indent=2))
