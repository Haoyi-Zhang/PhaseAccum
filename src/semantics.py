"""Exact finite binary semantics. No host floating-point arithmetic is used.

Mixed addition means exact addition of operand values followed by ONE target
rounding. It does not insert operand casts. Nonfinite values and signed-zero
observations are outside this numerical model.
"""
from __future__ import annotations
from dataclasses import dataclass
from fractions import Fraction

MODES = ('rne', 'rup', 'rdn', 'rtz')

def two(e: int) -> Fraction:
    return Fraction(1 << e, 1) if e >= 0 else Fraction(1, 1 << -e)

def floor_log2(x: Fraction) -> int:
    if x <= 0:
        raise ValueError('positive argument required')
    e = x.numerator.bit_length() - x.denominator.bit_length()
    return e - (x < two(e))

@dataclass(frozen=True)
class Format:
    p: int
    emin: int
    emax: int

    @classmethod
    def read(cls, data: dict) -> 'Format':
        if set(data) != {'p', 'emin', 'emax'}:
            raise ValueError('format fields')
        if any(type(data[k]) is not int for k in data):
            raise ValueError('integral format parameters required')
        f = cls(**data)
        if not (2 <= f.p <= 64 and -2048 <= f.emin <= f.emax <= 2048):
            raise ValueError('format resource boundary')
        return f

    @property
    def quantum(self) -> Fraction:
        return two(self.emin-self.p+1)

    @property
    def maximum(self) -> Fraction:
        return ((1 << self.p)-1)*two(self.emax-self.p+1)

    def round(self, x: Fraction, mode: str = 'rne') -> Fraction:
        if mode not in MODES:
            raise ValueError('rounding mode')
        if abs(x) > self.maximum:
            raise ValueError('outside finite numerical envelope')
        if x == 0:
            return Fraction(0)
        e = max(self.emin, floor_log2(abs(x)))
        h = two(e-self.p+1)
        t = x/h
        k, rem = divmod(t.numerator, t.denominator)
        if mode == 'rdn': n = k
        elif mode == 'rup': n = k + (rem != 0)
        elif mode == 'rtz': n = k + (x < 0 and rem != 0)
        else:
            twice = 2*rem
            n = k + (twice > t.denominator or
                     (twice == t.denominator and k % 2 != 0))
        return n*h

    def represents(self, x: Fraction) -> bool:
        return abs(x) <= self.maximum and self.round(x) == x


def lattice_round(t: int, m: int, mode: str, negative: bool = False) -> int:
    if m < 1 or m & (m-1):
        raise ValueError('power-of-two step required')
    k, r = divmod(t, m)
    if mode == 'rtz':
        mode = 'rup' if negative else 'rdn'
    if mode == 'rdn': n = k
    elif mode == 'rup': n = k + (r != 0)
    elif mode == 'rne': n = k + (2*r > m or (2*r == m and k % 2 != 0))
    else: raise ValueError('rounding mode')
    return n*m


def ceil_error_bit(units: int, delta_exp: int) -> int | None:
    if units == 0:
        return None
    if units < 0:
        raise ValueError('negative magnitude')
    return (units-1).bit_length()+delta_exp


def full_residual_alphabet_representable(f: Format, gap: int, delta_exp: int, mode: str) -> bool:
    """Exact full-alphabet test, NOT an implementation theorem for TwoSum.

    The grid is delta=2**delta_exp and the rounding spacing is 2**gap*delta.
    For fixed-sign RTZ, either directed alphabet has the same representability.
    This criterion can reject a sparse reachable residual set that still fits.
    """
    if type(gap) is not int or not 0 <= gap <= 8191:
        raise ValueError('residual gap')
    if type(delta_exp) is not int or not -2048 <= delta_exp <= 2048:
        raise ValueError('residual grid exponent')
    if mode not in MODES:
        raise ValueError('rounding mode')
    if gap == 0:
        return True
    bits = gap - 1 if mode == 'rne' else gap
    return (two(delta_exp) >= f.quantum and
            f.emax >= delta_exp + gap - 1 and f.p >= bits)
