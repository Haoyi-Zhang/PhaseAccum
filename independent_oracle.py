#!/usr/bin/env python3
"""Independent full-network oracle for the small exhaustive families.

This executable deliberately imports no project package.  It reconstructs the
finite binary formats by explicit value enumeration, replays every concrete row
of the declared two-gate census and the structurally disjoint three-gate
challenge family, and compares global and block relations with the retained
certificates.  It is finite differential evidence, not a general proof.
"""
from __future__ import annotations

import argparse
from bisect import bisect_left
from fractions import Fraction
from itertools import product
import json
from pathlib import Path
from typing import Any

Q = Fraction
VALUES: dict[tuple[int, int, int], tuple[Q, ...]] = {}
VALUE_SETS: dict[tuple[int, int, int], frozenset[Q]] = {}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def power(exponent: int) -> Q:
    return Q(1 << exponent, 1) if exponent >= 0 else Q(1, 1 << -exponent)


def format_key(fmt: dict[str, int]) -> tuple[int, int, int]:
    require(isinstance(fmt, dict) and set(fmt) == {"p", "emin", "emax"}, "format fields")
    require(all(type(fmt[name]) is int for name in fmt), "format parameter types")
    p, emin, emax = fmt["p"], fmt["emin"], fmt["emax"]
    require(2 <= p <= 8 and -16 <= emin <= emax <= 16, "oracle format boundary")
    return p, emin, emax


def explicit_values(fmt: dict[str, int]) -> tuple[Q, ...]:
    key = format_key(fmt)
    if key in VALUES:
        return VALUES[key]
    p, emin, emax = key
    positive = {Q(0)}
    quantum = power(emin - p + 1)
    positive.update(k * quantum for k in range(1, 1 << (p - 1)))
    for exponent in range(emin, emax + 1):
        spacing = power(exponent - p + 1)
        positive.update(k * spacing for k in range(1 << (p - 1), 1 << p))
    ordered = tuple(sorted(positive | {-value for value in positive}))
    VALUES[key] = ordered
    VALUE_SETS[key] = frozenset(ordered)
    return ordered


def explicit_round(value: Q, fmt: dict[str, int], mode: str) -> Q:
    require(mode in {"rne", "rup", "rdn", "rtz"}, "rounding mode")
    values = explicit_values(fmt)
    index = bisect_left(values, value)
    require(index < len(values), "rounding above finite envelope")
    if values[index] == value:
        return value
    require(index > 0, "rounding below finite envelope")
    low, high = values[index - 1], values[index]
    if mode == "rdn":
        return low
    if mode == "rup":
        return high
    if mode == "rtz":
        return low if value > 0 else high
    low_distance, high_distance = value - low, high - value
    if low_distance < high_distance:
        return low
    if high_distance < low_distance:
        return high
    lattice_index = low / (high - low)
    require(lattice_index.denominator == 1, "tie lattice index")
    return low if lattice_index.numerator % 2 == 0 else high


def max_finite(fmt: dict[str, int]) -> Q:
    p, _, emax = format_key(fmt)
    return ((1 << p) - 1) * power(emax - p + 1)


def cell_and_spacing(gate: dict[str, Any]) -> tuple[Q, Q, Q]:
    fmt = gate["format"]
    p, emin, emax = format_key(fmt)
    cell = gate["cell"]
    if cell.get("kind") == "normal":
        require(set(cell) == {"kind", "exponent", "sign"}, "normal cell fields")
        exponent, sign = cell["exponent"], cell["sign"]
        require(type(exponent) is int and emin <= exponent <= emax, "normal exponent")
        require(sign in {-1, 1}, "normal sign")
        low = power(exponent)
        high = min(power(exponent + 1), max_finite(fmt))
        if sign < 0:
            low, high = -high, -low
        spacing = power(exponent - p + 1)
        return low, high, spacing
    require(cell == {"kind": "subnormal"}, "subnormal cell fields")
    return -power(emin), power(emin), power(emin - p + 1)


def case_rows(case: dict[str, Any]):
    if "relation" in case:
        yield from (tuple(row) for row in case["relation"])
    else:
        yield from product(*(item["values"] for item in case["inputs"]))


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def independent_modulus(case: dict[str, Any]) -> int:
    delta = power(case["delta_exp"])
    modulus = 1
    for gate in case["gates"]:
        require(gate["kind"] == "add", "oracle family must contain additions only")
        _, _, spacing = cell_and_spacing(gate)
        ratio = spacing / delta
        require(ratio.denominator == 1 and ratio >= 1, "integer grid spacing")
        step = int(ratio)
        require(step & (step - 1) == 0, "power-of-two spacing")
        period = 2 * step if gate["mode"] == "rne" and step > 1 else step
        modulus = max(modulus, period)
    return modulus


def replay_case(case: dict[str, Any], certificate: dict[str, Any]) -> dict[str, int]:
    require(canonical(certificate["network"]) == canonical(case), "certificate/network binding")
    require(all(gate.get("kind") == "add" for gate in case["gates"]), "unsupported oracle gate")
    require(len(case["inputs"]) in {3, 4} and len(case["gates"]) in {2, 3}, "oracle family shape")
    delta = power(case["delta_exp"])
    modulus = independent_modulus(case)
    require(certificate["meta"]["modulus_units"] == modulus, "independent modulus disagreement")
    for item in case["inputs"]:
        values = VALUE_SETS.get(format_key(item["format"]))
        if values is None:
            explicit_values(item["format"])
            values = VALUE_SETS[format_key(item["format"])]
        for coordinate in item["values"]:
            require(coordinate * delta in values, "input not representable")

    boundaries = [0] + case["cuts"] + [len(case["gates"])]
    require(len(certificate["blocks"]) == len(boundaries) - 1, "block count")
    input_names = [item["name"] for item in case["inputs"]]
    observed: dict[tuple[int, ...], tuple[tuple[int, ...], int]] = {}
    block_maps: list[dict[tuple[int, ...], tuple[tuple[int, ...], int]]] = [
        {} for _ in range(len(boundaries) - 1)
    ]
    block_names: list[tuple[list[str], list[str]] | None] = [None] * (len(boundaries) - 1)
    concrete_rows = 0
    gate_checks = 0

    for coordinates in case_rows(case):
        concrete_rows += 1
        state = {name: coordinate * delta for name, coordinate in zip(input_names, coordinates)}
        original_sum = sum(state.values(), Q(0))
        loss = Q(0)
        for block_index, (begin, end) in enumerate(zip(boundaries, boundaries[1:])):
            incoming_names = sorted(state)
            incoming_key = tuple(int(state[name] / delta) % modulus for name in incoming_names)
            before = loss
            for gate_index in range(begin, end):
                gate_checks += 1
                gate = case["gates"][gate_index]
                argument = sum((state.pop(name) for name in gate["args"]), Q(0))
                low, high, _ = cell_and_spacing(gate)
                require(low <= argument <= high, "runtime outside declared cell")
                rounded = explicit_round(argument, gate["format"], gate["mode"])
                residual = argument - rounded
                require((rounded / delta).denominator == 1, "rounded grid closure")
                require((residual / delta).denominator == 1, "residual grid closure")
                state[gate["out"][0]] = rounded
                loss += residual
            outgoing_names = sorted(state)
            output_value = (
                tuple(int(state[name] / delta) % modulus for name in outgoing_names),
                int((loss - before) / delta),
            )
            previous = block_maps[block_index].get(incoming_key)
            require(previous is None or previous == output_value, "phase-functional block disagreement")
            block_maps[block_index][incoming_key] = output_value
            names = (incoming_names, outgoing_names)
            previous_names = block_names[block_index]
            require(previous_names is None or previous_names == names, "block port-name disagreement")
            block_names[block_index] = names
        require(original_sum - sum(state.values(), Q(0)) == loss, "conservation")
        source_key = tuple(coordinate % modulus for coordinate in coordinates)
        final_value = (
            tuple(int(state[name] / delta) % modulus for name in case["outputs"]),
            int(loss / delta),
        )
        previous = observed.get(source_key)
        require(previous is None or previous == final_value, "global phase quotient disagreement")
        observed[source_key] = final_value

    expected_rows = [
        {"in": list(key), "out": list(value[0]), "loss": value[1]}
        for key, value in sorted(observed.items())
    ]
    require(canonical(certificate["rows"]) == canonical(expected_rows), "global relation disagreement")
    block_rows = 0
    for index, block in enumerate(certificate["blocks"]):
        require(block_names[index] is not None, "empty block")
        incoming_names, outgoing_names = block_names[index]  # type: ignore[misc]
        rows = [
            {"in": list(key), "out": list(value[0]), "loss": value[1]}
            for key, value in sorted(block_maps[index].items())
        ]
        expected = {
            "begin": boundaries[index],
            "end": boundaries[index + 1],
            "in_names": incoming_names,
            "out_names": outgoing_names,
            "rows": rows,
        }
        require(canonical(block) == canonical(expected), "block relation disagreement")
        block_rows += len(rows)
    maximum = max(abs(value[1]) for value in observed.values())
    exponent = None if maximum == 0 else (maximum - 1).bit_length() + case["delta_exp"]
    require(certificate["max_abs_loss_units"] == maximum, "maximum loss disagreement")
    require(certificate["tight_power_two_exponent"] == exponent, "dyadic envelope disagreement")
    return {
        "concrete_rows": concrete_rows,
        "phase_rows": len(observed),
        "block_rows": block_rows,
        "gate_checks": gate_checks,
    }


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def load(path: Path):
    require(path.stat().st_size <= 64 * 1024 * 1024, "JSON size cap")
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", default="inputs/suite.json")
    parser.add_argument("--certificates", default="results/certificates.json")
    parser.add_argument("--output", default="results/independent-network-oracle.json")
    args = parser.parse_args()
    suite = load(Path(args.suite))
    certificates = load(Path(args.certificates))
    require(isinstance(suite, list) and isinstance(certificates, list), "top-level JSON arrays")
    require(len(suite) == len(certificates), "suite/certificate cardinality")
    ids = [case.get("id") for case in suite]
    require(len(ids) == len(set(ids)), "duplicate case identifier")
    by_id = {case["id"]: certificate for case, certificate in zip(suite, certificates)}
    selected = [
        case for case in suite
        if case["id"].startswith("census-") or case["id"].startswith("challenge-")
    ]
    require(len(selected) == 1184, "independent oracle family cardinality")
    totals = {"concrete_rows": 0, "phase_rows": 0, "block_rows": 0, "gate_checks": 0}
    family_counts = {"census": 0, "challenge": 0}
    for case in selected:
        family = "census" if case["id"].startswith("census-") else "challenge"
        family_counts[family] += 1
        row = replay_case(case, by_id[case["id"]])
        for name in totals:
            totals[name] += row[name]
    require(family_counts == {"census": 864, "challenge": 320}, "family split")
    require(totals["concrete_rows"] == 12032, "independent oracle concrete-row count")
    require(totals["gate_checks"] == 29184, "independent oracle gate-check count")
    result = {
        "status": "passed",
        "scope": ("Independent explicit-format replay of the complete declared two-gate census "
                  "and the deterministic three-gate structural challenge; not a general proof "
                  "or an external replication."),
        "imports_project_code": False,
        "families": family_counts,
        "networks": len(selected),
        **totals,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, TypeError, KeyError, IndexError, OverflowError) as exc:
        raise SystemExit("INDEPENDENT ORACLE FAILED: " + str(exc))
