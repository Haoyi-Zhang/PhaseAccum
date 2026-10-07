# Mathematical basis of residual-phase contracts

These are exact-number arguments, not a machine-checked proof development. The finite tests use separately implemented numerical routes on specified examples; they do not replace any parameterized proof below.

## 1. Model and conservation

A binary format `(p, emin, emax)` contains zero, normals `n*2^(e-p+1)` for `2^(p-1) <= n < 2^p` and `emin <= e <= emax`, subnormals `n*2^(emin-p+1)` for `0 < n < 2^(p-1)`, and their negatives. Precision is at least two, signed zeros are identified, and rounded arguments stay inside the finite envelope. Nearest ties select the adjacent value with even lattice index; directed modes have their ordinary order meaning.

Each gate has a certified fixed-spacing cell. On that cell, format rounding equals rounding to one uniform lattice, including shared endpoints. A toward-zero cell also fixes the argument sign. Inputs are multiples of a common dyadic unit `delta`, and every gate spacing is a power-of-two integer multiple of `delta`. Gates consume live wires once and create fresh outputs. Addition and cast round once; a split returns a rounded sum and its exact residual in separately declared formats; a discard removes a value. Constants count as original inputs.

Let `S` be the exact original input sum and let `D` be `S` minus the sum of live values, measured in `delta` units. Initially `D=0`. Replacing an exact gate argument `t` by `R(t)` increases `D` by `(t-R(t))/delta`. A split preserves the combined live sum; discarding `v` adds `v/delta`. Induction over the topological order proves conservation and final signed sum error `-delta*D`. The maximum absolute error on a nonempty finite relation is `delta*max |D|`. Zero means exactness; otherwise the tight dyadic envelope is the smallest power of two not below that value.

## 2. Exactly one additional phase bit

Fix `q>=4`, `k>=1`, `m=2^k`, `N=2m`, target spacing `h`, fine spacing `delta=h/m`, and `A=2^(q-1)h`. Source precision is `p=q+k`, with ranges supporting the displayed values. Let `x_r=A+r*delta` for `0<=r<N`. For `0<=t<N`, define

`C_t(x)=RN_h(RN_h(x+t*delta)+h/2)`

and observe whether its absolute error against `x+t*delta+h/2` is at most `h/2`. All exact and rounded arguments remain in one normal cell.

For `j=(r+t) mod 2m`, translation by `2h` reduces the calculation to `0<=j<2m`. The first round returns offsets `0`, `m`, or `2m` across the two nearest-even midpoint boundaries. Adding `m/2` and rounding again returns `0` in the first case and `2m` in the other cases. The final error is at most `m/2` exactly when `j=0` or `m<=j<2m`.

For two phases `r != s`, let `a=(s-r) mod 2m`. If `1<=a<=m`, choose `t=(m-1-r) mod 2m`; the phases become `m-1` and a point in `[m,2m-1]`. If `m<a<2m`, choose `t=(1-r) mod 2m`; the phases become `1` and a point in `{0} union [m+2,2m-1]`. The Boolean observation differs in either case. Thus all `2m=2^(k+1)` points are pairwise distinguishable. The residue modulo `2m` is also a sufficient evaluator state, so the lower bound is exact.

For one translated addition, absolute error is distance to `h*Z`, with period `h`; hence `r` and `r+m` are indistinguishable under every translation and dyadic threshold. Distinct residues modulo `m` are separated by translating one point to the coarse lattice and using threshold `delta/2`. There are exactly `m=2^k` classes. Two additions are therefore the worst-case shortest separating length in this observation family, not the minimum length for every pair or every circuit language.

For `w` independently varying ports, two distinct tuples differ in some coordinate. Apply that coordinate's separator and pass the others unchanged; their computed and ideal contributions cancel. All `(2m)^w` tuples are distinguishable for a continuation family allowed to select any port.

For `k>=2`, the same sign/exponent/bit-run collision is

`x=1+2h+delta`, `x'=1+3h+delta`, `c=h/2-delta`, `d=h/2`, with `h=2^(1-q)`.

The first rounded sums are `1+2h` and `1+4h`; the second nearest-even ties retain them. Final absolute errors are `h` and zero. This disproves exactness of that point interface for this observation, not soundness of an overapproximate verifier.

## 3. Least residual periods

For the network model, the integer lattice spacing `m` is a power of two. Write `t=m*u+v` with `0<=v<m`, let `Q_m^R(t)` be rounded output, and set `rho_m^R(t)=t-Q_m^R(t)`.

For directed rounding, the decision depends only on whether `v=0` and on the declared direction, so shifting by `m` preserves `rho`. For fixed-sign toward-zero, the corresponding directed rule applies. For nearest-even, non-midpoint decisions depend only on `v`; a midpoint additionally reads the parity of `u`, which is preserved by shifting `2m`. Thus `m` is a residual period for directed/fixed-sign toward-zero and `2m` is a period for nearest-even.

These periods are least. The zero set of every residual map is exactly `m*Z`; translation by any positive period must preserve that set, so the period is a multiple of `m`. For directed modes, `m` is therefore least. When the power-of-two spacing has `m>=2`, evaluate nearest-even at `t=m/2`: it rounds to the even-index lattice point zero and has residual `+m/2`; after a shift by `m`, the midpoint lies between odd index one and even index two, giving residual `-m/2`. Hence `m` is not a nearest-even period and `2m` is least. At `m=1`, every grid integer is exact and the least positive period is one.

## 4. Exact composition and a depth-independent alphabet

Choose a power-of-two `B` divisible by every gate's least period and larger than every discard window width. Retain the ordered tuple of live values modulo `B` together with signed loss `D`. For addition, form the sum of operand phases, round it on the declared lattice, emit the rounded phase, and add the residual to `D`; casts are unary. A split emits the rounded phase and residual phase without changing `D`, provided the exact residual is representable. For a discard with phase `r` and enclosure `[a,b]`, reconstruct the unique value

`a + ((r-a) mod B)`

and require it not to exceed `b`; uniqueness follows because the window is narrower than `B`.

For local commutation, the concrete integer argument `T` and phase representative `t` differ by a multiple of `B`. Residual periodicity yields `T-Q(T)=t-Q(t)` and congruent rounded outputs. The cell guard identifies lattice and format rounding; the split and discard obligations handle their additional cases. Therefore each abstract gate returns exactly the concrete output phases and loss increment.

A block contract is a relation `(incoming joint phase, outgoing joint phase, signed loss increment)`. Composition joins the complete intermediate tuple and adds increments. Starting from the exact phase image of a finite input relation and `D=0`, induction gives every concrete row. Conversely, local commutation makes each guarded block a function of its reachable incoming joint phase; joining a reachable boundary phase therefore applies the same downstream output and increment to every concrete representative of that phase, rather than inventing a cross-witness behavior. Loss increments telescope, and integer addition is associative; every consecutive block partition yields the same global relation and exact error bound.

The same argument makes a guarded block functional on its reachable incoming phase tuples: every gate transfer is functional, and functional composition remains functional. An exact table may therefore deduplicate concrete source rows by incoming phase, provided source-indexed coverage still proves that no input row was omitted. This does not license coordinate-wise marginals, which can invent joint tuples with no concrete witness. The checker enforces exactly this distinction by requiring rows with a shared block input phase to agree on output and loss increment while separately checking source coverage.

For example, nearest-even spacing `8*delta`, downward spacing `16*delta`, and upward spacing `4*delta` have least periods 16, 16, and 4, so `B0=16`. Any discard-free continuation using only those cells observes one varying source through phase modulo 16 regardless of depth. Adding gates at existing spacings does not enlarge the per-source alphabet; admitting nearest-even spacing `16*delta` can enlarge it to 32. Thus the mode/spacing set, rather than depth alone, controls this alphabet.

The association is necessary. For nearest-even spacing one, take `delta=1/16` and `B=32`. In real units, cut states `(phase,loss)=(0,-1/4)` and `(1,+1/4)` receive later increments `+1/2` and `-1/2`, respectively, so actual final losses are only `+/-1/4`. Multiplying phase and loss marginals also admits `+/-3/4`, increasing the dyadic envelope by two bits.

For a finite set of spacing/mode pairs, define `b(m,R)=2m` for nearest-even with `m>1` and `b(m,R)=m` otherwise, and let `B0` be their maximum. Because all values are powers of two, `B0` is a common multiple of every least period. Consider a discard-free continuation with one varying source, fixed other sources, valid local obligations, and initial loss zero. Two source values equal modulo `B0` induce identical initial phase states; exact composition gives identical final loss at every depth. Thus the source phase modulo `B0` determines final signed sum error independently of depth.

The bound is sharp for the stated retained families. If the full family of translated directed additions at spacing `B0` is allowed, translate either member of a phase pair onto the lattice: its residual is zero and the other residual is nonzero, so a `delta/2` absolute-error threshold separates them. If `B0` is attained only by nearest-even spacing `B0/2`, the two-addition separator above distinguishes all `B0` phases. The `B0=1` case is exact. This is a per-source alphabet result, not a compact joint-state guarantee: `w` independent ports may require `B0^w` tuples, and signed loss remains an associated state component. Discards are excluded because their value reconstruction can require a larger modulus.

With `N` initial phase rows and `g` gates, deterministic explicit transfer performs at most `N*g` row transfers and retains at most `N` reachable joint rows at a cut before duplicate removal. This does not establish dense scalability.

## 5. Residual-format criterion

Let `m=2^k`, `k>=1`, and `delta=2^d`. The full nearest-even residual alphabet is `{n*delta : -2^(k-1)<=n<=2^(k-1)}`. Downward residuals have `0<=n<2^k`; upward residuals are their negatives, and fixed-sign toward-zero is directed. Let the residual format have quantum `eta`, precision `p_r`, and maximum normal exponent `emax_r`.

The full nearest alphabet is representable exactly iff

- `delta>=eta`,
- `emax_r>=d+k-1`, and
- `p_r>=k-1`.

The values `delta` and `2^(k-1)delta` force the quantum and exponent conditions. For `k>=3`, `(2^(k-1)-1)delta` has `k-1` significant bits and forces the precision condition; for `k<=2`, format precision at least two already suffices. Conversely, removing powers of two from any coefficient leaves at most `k-1` significant bits, while the quantum and exponent conditions cover subnormal alignment, normals, and the endpoint.

For a directed alphabet, replace the precision condition by `p_r>=k`. The odd endpoint coefficient `2^k-1` forces `k` bits; every other coefficient uses no more. At `k=0`, only zero occurs. This is a full-alphabet criterion; a sparse reachable subset can fit a weaker format. It is not a concrete EFT implementation theorem.

## 6. Fixed-parameter linear encoding

For fixed `m` and `B`, quotient/remainder constraints `t=m*u+v`, `0<=v<m` are linear integer constraints. Nearest selection uses `2v<m`, `2v>m`, and a midpoint disjunction on the parity of `u`; directed selection uses `v=0` or `v>0`. Output phase satisfies `q=z+B*a`, `0<=z<B`. Loss updates, wire equalities, finite input-row selection, and discard reconstruction are also linear.

Conjoining these clauses expresses guarded network reachability with internal variables. Hiding internal wires is existential projection and need not preserve formula size. Enumerating the exact finite boundary relation gives a quantifier-free disjunction, potentially large. Format-parametric construction substitutes fixed powers of two first; `2^p` with variable `p` is not linear. No solver execution or solver-performance conclusion follows.
