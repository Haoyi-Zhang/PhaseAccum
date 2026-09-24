# Numerical inputs and certificates

## Input relation

A suite is a JSON list of cases. A case has exactly the required keys `id`, `delta_exp`, `inputs`, `gates`, `outputs`, and `cuts`, with optional `relation`. Names are case-sensitive. An integer input value `v` denotes the exact real `v * 2**delta_exp`. JSON booleans and floating-point literals are not integers in this schema.

An input entry has `name`, `format`, and a nonempty duplicate-free list `values`. A format has exactly integral `p`, `emin`, `emax`. With no `relation`, the input domain is the Cartesian product in declared input order. With `relation`, only its explicitly listed rows are admitted; every component must belong to its input's support. These two interpretations must not be interchanged. Constants are singleton-support inputs and participate in the ideal input sum.

The implementation bounds are 1–8 inputs, 1–4,096 values per input, at most 12,000 concrete rows and 12,000 initial phase rows, 0–64 gates, depth at most 32, and at most eight distinct formats. Format precision is 2–64; exponent parameters and the common-grid exponent lie in [-2048,2048]. Integer magnitudes and the modulus are capped at 8,192 bits. The serialized checker limits each input JSON file to 32 MiB. Duplicate object keys are rejected. These are implementation limits, not theorem hypotheses about all finite precisions.

## Gates and guards

Every gate has `kind`, `args`, and `out`. Rounded gates additionally have `format`, `mode`, and `cell`. The modes are `rne`, `rup`, `rdn`, `rtz`. A normal cell is `{"kind":"normal","exponent":e,"sign":1}` or sign `-1`; the positive interval is `[2**e, min(2**(e+1), maximum)]`. A central cell is `{"kind":"subnormal"}` and includes `[-2**emin,2**emin]`. Shared endpoints are exact. Toward-zero rounding additionally requires the propagated argument enclosure to have one sign. The common grid cannot be coarser than the cell's spacing.

An `add` consumes two distinct live wires and creates one fresh output. A `cast` consumes one and creates one. A `split` consumes two and creates two, with `residual_format` declaring where the exact second output must fit. The split is not an instruction sequence. A `drop` consumes one and creates none; it has an integral `window:[a,b]` instead of rounding fields. The propagated enclosure must be inside that window.

Wire consumption is unique: reusing a consumed wire, duplicating an argument, aliasing an output, or omitting an unconsumed final wire is rejected. `outputs` lists all and only the surviving wires. `cuts` is a sorted duplicate-free list of proper interior gate positions, defining consecutive blocks. Empty cuts produce one block, including the zero-gate identity case.

Interval propagation is deliberately nonrelational. A correlated input relation may have a valid guard that this sufficient procedure cannot certify. Such a case is rejected, not silently accepted on a guessed guard. Residual representability is checked on the actually reached phases; a full-alphabet criterion is a separate stronger test.

## Phase tables

The modulus `B` is a power of two covering all local residual periods: `2*m` for nontrivial nearest-even gates and `m` for directed or fixed-sign toward-zero gates. It is enlarged until every drop window has width less than `B`. Phases are canonical residues in `[0,B)`. Signed losses are in the original common-grid units, not reduced modulo `B`.

Each certificate embeds its exact `network`, recomputed `meta`, `blocks`, source-indexed composed `rows`, maximum absolute loss in integer units, and the least dyadic envelope exponent. Each block records its start/end, ordered live port names, and complete rows with `in`, `out`, and signed `loss` increment. All states are joint tuples; accumulated loss remains associated with its phase tuple. Names and wire order are part of the contract.

The checker binds the embedded network to the supplied case and recomputes numerical and structural facts rather than trusting the producer metadata. It verifies complete input-phase coverage, the required block rows, composed output phases and losses, concrete replay, and the tight bound. A zero error has exponent `null`, meaning exactness; it has no least integer dyadic exponent.

## Trust and failure

The independent implementation boundary is at Python modules, not personnel or proof kernels. The checker does not import `semantics.py`, `phase.py`, or `fixtures.py`, but it was developed within the same study. Python integer/rational operations, interpreter behavior, the host, and the completeness of the checker specification remain trusted.

A rejected mutation is evidence about that concrete mutation, not a universal guarantee against arbitrary malformed input. The tools are research programs for the retained local inputs, not hardened untrusted-service endpoints. `reproduce.py` applies process limits; direct module invocation does not. No exception behavior of an actual floating-point processor is inferred from parser or model rejection.
