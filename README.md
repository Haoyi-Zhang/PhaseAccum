# Reproducible residual-phase contract artifact

This repository accompanies *Residual-Phase Contracts for Guarded Mixed-Format Accumulation*. It implements exact rational semantics for the paper's guarded finite model, constructs residual-phase contracts, and checks serialized certificates with separately implemented numerical code.

The artifact is evidence for specified finite instances. It is **not** a proof assistant development, an IEEE hardware conformance suite, a performance benchmark, or a linker for independently generated contracts.

## One-command reproduction

From this directory, run:

```sh
python reproduce.py
```

The standard-library-only wrapper uses one worker, a 110-second lifecycle deadline, a 2 GiB child address-space limit, and six fail-closed stages:

1. bibliography and calibration inventory audit;
2. 28 unit-test methods in normal interpreter mode;
3. the identical 28-test suite under `python -O`;
4. deterministic campaign generation;
5. an independent explicit-format whole-network oracle for the two exhaustive families;
6. standalone serialized-certificate replay.

Every stage writes its stdout and stderr under `results/`. `results/python-runtime.json` records the interpreter version and measured normal/optimized flags; `results/reproduction.json` records each exact command, optimization level, exit code, log path, and resource measurement. Both files are regenerated, so an interrupted run cannot be mistaken for an earlier success.

## Retained finite evidence

A successful campaign retains:

- 1,285 networks and 24,700 concrete input rows;
- 15,900 initial joint-phase rows and 22,066 exported block rows;
- a complete 864-network three-input/two-gate census with 6,912 rows;
- a structurally different complete 320-network four-input/three-gate challenge with 5,120 rows;
- an explicit-format whole-network oracle over all 1,184 census/challenge networks, 12,032 concrete rows, and 29,184 gate evaluations;
- maximum executed size of 32 gates and depth 32;
- 21,840 phase/context observations, each checked against formula (10), six explicit one-addition class-count checks, and 21,588 constructive separator checks;
- 4,224 three-way exact rounding comparisons over four complete small formats;
- 400 residual-alphabet configurations and 5,160 explicit membership checks;
- 35 least-period configurations and 3,770 periodicity/minimality checks;
- four standard-format residual witnesses;
- one targeted observation-word bit mutation rejected by the full formula check, plus 20 rejected certificate mutations and five rejected unsupported networks;
- 94,067 designated finite obligations, below the project ceiling of 100,000.

The 32-gate positive chain is additionally replayed under four cut partitions. Their local tables contain 4, 32, 128, and 32 rows, but all yield the same four-row global relation and maximum loss of three grid units.

## Independence and test-selection boundary

`src/phase.py` is the producer. `src/checker.py` imports no producer or project numerical module: it locates neighboring finite-format values and rounds exact rationals directly. `independent_oracle.py` imports no project module, explicitly enumerates every representable value of each retained small format, and replays whole networks.

These are implementation-separated paths, not an external replication. They share the paper's specification and were authored in one project, so a common conceptual mistake can survive. The structurally different challenge reduces fixture coupling but was designed during artifact review and is not described as a blind statistical holdout. No statistical model is trained; “overfitting” is addressed by exhaustive declared axes, topology/cell/precision separation, independent implementations, mutation tests, and clean reruns rather than by train/test accuracy.

## Main files

- `src/semantics.py` — exact binary formats and rounding.
- `src/phase.py` — guarded contract producer.
- `src/checker.py` — standalone concrete certificate checker.
- `independent_oracle.py` — explicit-format independent whole-network replay.
- `src/fixtures.py` — targeted, census, challenge, and rejected cases.
- `src/campaign.py` — deterministic evidence generation and mutations.
- `tests/test_core.py` — exact semantics, topology, parser, and optimized-Python tests.
- `inputs/suite.json` — frozen generated network suite.
- `results/` — certificates, raw summaries, logs, and evidence tables.
- `claim_evidence_ledger.csv` — claim-to-proof/check/result mapping.
- `reference_audit.csv` and `external_resources.csv` — bibliography and source-access records.
- `docs/proofs.md`, `docs/schema.md`, `docs/resources.md`, `docs/trust-boundary.md`, `docs/reference-verification.md` — mathematical and reproducibility notes.

## Scope

The model assumes a finite input relation, conservative acyclic wiring, a common dyadic grid, independently established fixed-spacing rounding cells, fixed sign for toward-zero cells, and representable exact residuals. It excludes NaNs, infinities, flags, overflow responses, flushing, implicit casts, arbitrary control flow, target-specific instructions, and independent linking of untrusted contracts.

Python 3.10 or later on POSIX/Linux is expected. No network access, package installation, solver, GPU, private data, or external service is used.
