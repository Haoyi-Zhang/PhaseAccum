#!/usr/bin/env python3
"""Reproduce the finite study with one worker and an end-to-end child deadline.

Linux/POSIX, Python standard library only. A fresh status record prevents a
failed rerun from being mistaken for a successful older campaign.
"""
from __future__ import annotations
import json
import os
import platform
import resource
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / 'results'

def limits() -> None:
    if hasattr(os, 'sched_setaffinity'):
        os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))
    resource.setrlimit(resource.RLIMIT_CPU, (100, 100))
    resource.setrlimit(resource.RLIMIT_FSIZE, (48 * 1024**2, 48 * 1024**2))

def child_environment() -> dict[str, str]:
    env=dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1',
             PYTHONDONTWRITEBYTECODE='1')
    # Make the normal and -O modes explicit rather than inheriting a caller flag.
    env.pop('PYTHONOPTIMIZE',None)
    return env


def runtime_probe(optimize: bool) -> dict:
    args=[sys.executable]
    if optimize:
        args.append('-O')
    args.extend(['-c', ('import json,platform,sys; '
                        'print(json.dumps({"implementation":platform.python_implementation(),'
                        '"python_version":platform.python_version(),'
                        '"optimize":sys.flags.optimize}))')])
    completed=subprocess.run(args,cwd=ROOT,env=child_environment(),capture_output=True,
                             text=True,timeout=5,preexec_fn=limits,check=False)
    if completed.returncode!=0:
        raise RuntimeError('Python runtime probe failed: '+completed.stderr.strip())
    data=json.loads(completed.stdout)
    expected=1 if optimize else 0
    if data.get('optimize')!=expected:
        raise RuntimeError(f'Python optimization probe expected {expected}, got {data!r}')
    data.update({'command':args,'exit_code':completed.returncode})
    return data


def snapshot(record: dict) -> None:
    tmp = RESULTS / '.reproduction.json.tmp'
    tmp.write_text(json.dumps(record, indent=2, sort_keys=True) + '\n')
    tmp.replace(RESULTS / 'reproduction.json')

def run(name: str, args: list[str], seconds: float) -> dict:
    if seconds <= 0:
        raise TimeoutError('no lifecycle budget remains')
    env=child_environment()
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    start = time.monotonic()
    timeout = False
    stdout = RESULTS / (name + '.stdout.txt')
    stderr = RESULTS / (name + '.stderr.txt')
    with stdout.open('wb') as out, stderr.open('wb') as err:
        p = subprocess.Popen([sys.executable] + args, cwd=ROOT, env=env,
                             stdout=out, stderr=err, start_new_session=True,
                             preexec_fn=limits)
        try:
            code = p.wait(timeout=seconds)
        except subprocess.TimeoutExpired:
            timeout = True
            try:
                os.killpg(p.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            code = p.wait()
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    optimization_level=1 if '-O' in args else (2 if '-OO' in args else 0)
    return {'command': [sys.executable] + args, 'exit_code': code, 'timed_out': timeout,
            'python_version':platform.python_version(),
            'optimization_level':optimization_level,
            'wall_seconds': time.monotonic() - start,
            'child_cpu_seconds': (after.ru_utime + after.ru_stime
                                  - before.ru_utime - before.ru_stime),
            'stdout': str(stdout.relative_to(ROOT)),
            'stderr': str(stderr.relative_to(ROOT))}

def main() -> int:
    RESULTS.mkdir(exist_ok=True)
    start = time.monotonic()
    parent_cpu = time.process_time()
    deadline = start + 110
    record = {'status': 'running', 'steps': [], 'workers': 1,
              'wall_limit_seconds': 110, 'child_address_space_limit_bytes': 2 * 1024**3,
              'claim': 'Finite exact-rational replay; not a mechanized general proof.'}
    snapshot(record)
    try:
        runtime={'normal':runtime_probe(False),'optimized':runtime_probe(True)}
        runtime_path=RESULTS/'python-runtime.json'
        runtime_path.write_text(json.dumps(runtime,indent=2,sort_keys=True)+'\n')
        record['python_runtime']='results/python-runtime.json'
        record['python_version']=runtime['normal']['python_version']
        record['optimized_python_level']=runtime['optimized']['optimize']
        snapshot(record)
    except Exception as exc:
        record['status']='failed'
        record['failure']=str(exc)
        record['wall_seconds']=time.monotonic()-start
        record['parent_cpu_seconds']=time.process_time()-parent_cpu
        record['total_cpu_seconds']=record['parent_cpu_seconds']
        record['peak_child_rss_kib']=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
        snapshot(record)
        print(json.dumps(record,indent=2,sort_keys=True))
        return 1
    commands = [
        ('bibliography', ['src/bibliography_audit.py'], 10),
        ('tests', ['-m', 'unittest', 'discover', '-s', 'tests', '-v'], 20),
        ('tests-optimized', ['-O', '-m', 'unittest', 'discover', '-s', 'tests', '-v'], 20),
        ('campaign', ['-m', 'src.campaign'], 100),
        ('independent-oracle', ['independent_oracle.py', '--suite', 'inputs/suite.json',
                                '--certificates', 'results/certificates.json'], 40),
        ('replay', ['src/checker.py', '--suite', 'inputs/suite.json',
                    '--certificates', 'results/certificates.json'], 100),
    ]
    try:
        for name, args, maximum in commands:
            step = run(name, args, min(maximum, deadline - time.monotonic()))
            record['steps'].append(step)
            snapshot(record)
            if step['exit_code'] != 0 or step['timed_out']:
                raise RuntimeError(name + ' failed; inspect its retained logs')
        record['status'] = 'passed'
        code = 0
    except Exception as exc:
        record['status'] = 'failed'
        record['failure'] = str(exc)
        code = 1
    finally:
        record['wall_seconds'] = time.monotonic() - start
        record['parent_cpu_seconds'] = time.process_time() - parent_cpu
        record['total_cpu_seconds'] = (record['parent_cpu_seconds']
                                      + sum(s['child_cpu_seconds'] for s in record['steps']))
        record['peak_child_rss_kib'] = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
        snapshot(record)
    print(json.dumps(record, indent=2, sort_keys=True))
    return code

if __name__ == '__main__':
    raise SystemExit(main())
