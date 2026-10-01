# Trust boundary and threats to validity

## Mathematical layer

The paper's general claims rest on explicit proofs. Executable evidence is not promoted to a theorem. The proof model assumes exact real arithmetic, a common dyadic grid, fixed-spacing guarded cells, conservative acyclic wiring, fixed sign for toward-zero cells, representable residuals, and a finite input relation for exact tabulation.

## Implementation layers

Three numerical routes are retained:

1. the quotient/remainder producer in `src/semantics.py` and `src/phase.py`;
2. the neighboring-value certificate checker in `src/checker.py`, which imports no project module;
3. the explicit-format whole-network oracle in `independent_oracle.py`, which imports no project module and enumerates complete small formats.

The implementations are separated, but all were written within the same project and share the mathematical specification. A shared conceptual error can therefore survive. The artifact does not describe them as third-party or independently authored verification.

## Fixture coupling and the overfitting analogue

No statistical model is fitted. The nearest analogue of overfitting is code tailored to a narrow fixture family. The artifact counters that risk with:

- exhaustive Cartesian axes for a declared 864-network two-gate family;
- a separate exhaustive 320-network three-gate family with four inputs, five tree shapes, normal and subnormal regimes, two precision schedules, two signs, and eight mode schedules;
- a whole-network oracle that replays both families through a different implementation;
- targeted deep, serial, balanced, residual, discard, and correlation cases;
- certificate mutations and fail-closed unsupported cases;
- a retained `python -O` rerun of the complete unit suite, with interpreter, command, exit, and log records, plus clean-extraction reruns.

The challenge family was designed during review, not reserved before development, so it is not called a blind holdout. Exhaustiveness applies only to the axes named in its result JSON, not all networks, formats, values, or IEEE behaviors.

## Remaining external validity limits

The largest executed network has 32 gates and depth 32. Dense joint phase tables can grow exponentially in the number of live ports. The artifact makes no claim about deployed-program prevalence, solver speed, hardware performance, exception behavior, compiler transformations, or independent contract linking.
