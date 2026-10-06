# Resource and reproducibility boundary

## Intake and caps

The retained intake is in `results/resource-intake.json`. The campaign intentionally uses one worker. The wrapper applies a 2 GiB child address-space limit, 100 CPU-second child limit, 48 MiB per-child output-file limit, and 110-second aggregate lifecycle deadline. The schema caps a case at 64 gates, depth 32, eight input ports, eight distinct formats, 12,000 concrete rows, and 12,000 phase rows. The final suite contains 1,285 networks and 94,067 designated obligations, below the project limits of 2,000 networks and 100,000 obligations.

## Pilot

`python src/pilot.py` replays the phase-separation family for precision gaps 1 through 6 with an explicitly enumerated neighboring-value oracle. It obtains 4, 8, 16, 32, 64, and 128 two-addition classes, versus 2, 4, 8, 16, 32, and 64 one-addition classes. The retained run used one worker, 0.647 wall seconds, 0.643 CPU seconds, and 93,360 KiB peak RSS.

## Full campaign

The final deterministic campaign reports:

- 1,285 networks and 24,700 concrete rows;
- 15,900 initial joint-phase rows and 22,066 block rows;
- 864 complete census networks and 320 complete structural-challenge networks;
- 32 maximum gates and depth 32;
- 21,840 observation bits individually checked against formula (10), six one-addition class counts checked against `m`, and 21,588 pair separators;
- 4,224 complete-small-format three-way rounding comparisons;
- 5,160 residual membership checks and 3,770 least-period checks;
- one targeted observation-word mutation regression, 20 rejected certificate mutations, and five rejected unsupported cases;
- 94,067 designated finite obligations;
- 122,805 base-checker round calls and 68,104 base-checker gate checks;
- 7.042 wall seconds, 7.042 CPU seconds, and 156,524 KiB peak child RSS in the retained campaign run.

The independent whole-network oracle separately replays 1,184 networks, 12,032 concrete rows, and 29,184 gate operations. It does not count as additional networks in the primary suite.

## End-to-end wrapper

The retained historical Linux six-stage `python reproduce.py` run records 29.466 wall seconds, 26.807 aggregate parent-plus-child CPU seconds, and 156,524 KiB peak child RSS. Exact timings vary by host and are measurements, not performance claims. Early exploratory work was not cumulatively metered.

The six stages are bibliography audit, 28 normal-mode unit tests, the identical 28 tests under `python -O`, campaign generation, independent whole-network replay, and standalone certificate replay. All six exited with code zero. `results/python-runtime.json` records CPython 3.13.5 with optimization levels 0 and 1; `results/reproduction.json` records the exact commands, exit codes, and normal/optimized log paths. Production source is also checked not to contain Python `assert` statements.

## Trust and portability

All arithmetic is based on Python integers and `fractions.Fraction`; no host binary floating-point value participates in semantic decisions. The trusted execution base includes the Python runtime, JSON parser, filesystem, and operating system. The artifact is POSIX-oriented because resource limits and process groups are used. It does not use network access, random seeds, external solvers, GPUs, swap, package installation, model APIs, or private data.

Finite replay checks implementation consistency on specified domains. It does not prove the parameterized theorems, represent real-world workload frequencies, certify hardware, or estimate a defect probability.
