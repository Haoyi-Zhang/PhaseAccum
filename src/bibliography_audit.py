#!/usr/bin/env python3
"""Audit the retained scholarly-source inventory and calibration matrix.

This is a deterministic structural audit of the shipped CSV evidence. It checks
identity, required fields, calibration counts, bounded-access disclosures, and a
few corrected high-risk identifiers. It does not pretend to replace scholarly
reading or live publisher metadata resolution.
"""
from __future__ import annotations

import csv
import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"


def read_rows(name: str) -> list[dict[str, str]]:
    path = ROOT / name
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"{name}: no rows")
    return rows


def require_fields(name: str, rows: list[dict[str, str]], fields: tuple[str, ...]) -> None:
    for index, row in enumerate(rows, start=2):
        missing = [field for field in fields if not row.get(field, "").strip()]
        if missing:
            raise ValueError(f"{name}:{index}: missing {', '.join(missing)}")


def valid_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc) and "placeholder" not in value.lower()


def complete(row: dict[str, str]) -> bool:
    text = " ".join((row["acquisition_method"], row["reading_status"])).lower()
    return "complete paper" in text or "complete pdf" in text


def main() -> int:
    refs = read_rows("reference_audit.csv")
    sources = read_rows("external_resources.csv")
    contexts = read_rows("citation_contexts.csv")
    require_fields(
        "reference_audit.csv",
        refs,
        (
            "cite_key",
            "entry_type",
            "year",
            "authors",
            "title",
            "publication",
            "manuscript_locations",
            "verification_scope",
        ),
    )
    require_fields(
        "citation_contexts.csv",
        contexts,
        ("cite_key", "source_file", "line_number", "context"),
    )
    require_fields(
        "external_resources.csv",
        sources,
        (
            "name",
            "url",
            "license",
            "access_date",
            "resource_type",
            "acquisition_method",
            "integration_mode",
            "supported_claim",
            "internals_modified",
            "reading_status",
        ),
    )

    keys = [row["cite_key"].strip() for row in refs]
    if len(refs) != 59:
        raise ValueError(f"expected the frozen 59-reference inventory, found {len(refs)}")
    if len(keys) != len(set(keys)):
        duplicates = sorted(key for key, count in Counter(keys).items() if count > 1)
        raise ValueError(f"duplicate cite keys: {duplicates}")
    if not all(re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", key) for key in keys):
        raise ValueError("invalid cite key")
    if any(not row["year"].isdigit() or not (1900 <= int(row["year"]) <= 2026) for row in refs):
        raise ValueError("reference year outside audited range")

    missing_identifiers = [row["cite_key"] for row in refs if not row["persistent_identifier"].strip()]
    if missing_identifiers != ["wilkinson1963"]:
        raise ValueError(f"unexpected references without persistent identifiers: {missing_identifiers}")
    identifiers = [row["persistent_identifier"].strip().lower() for row in refs
                   if row["persistent_identifier"].strip()]
    duplicate_identifiers = sorted(value for value, count in Counter(identifiers).items() if count > 1)
    if duplicate_identifiers:
        raise ValueError(f"duplicate persistent identifiers: {duplicate_identifiers}")
    normalized_titles = [re.sub(r"[^a-z0-9]+", "", row["title"].lower()) for row in refs]
    duplicate_titles = sorted(title for title, count in Counter(normalized_titles).items() if count > 1)
    if duplicate_titles:
        raise ValueError(f"duplicate normalized titles: {duplicate_titles}")
    if any(not row["manuscript_locations"].strip() for row in refs):
        raise ValueError("every reference must have a manuscript citation location")
    context_keys = [row["cite_key"].strip() for row in contexts]
    if set(context_keys) != set(keys):
        missing = sorted(set(keys) - set(context_keys))
        extra = sorted(set(context_keys) - set(keys))
        raise ValueError(f"citation-context key mismatch: missing={missing}, extra={extra}")
    for row in contexts:
        if not row["source_file"].startswith("paper/"):
            raise ValueError("citation context must name a paper-relative source")
        if not row["line_number"].isdigit() or int(row["line_number"]) < 1:
            raise ValueError("invalid citation-context line number")
        if "\\cite" not in row["context"]:
            raise ValueError("citation context does not contain a citation command")

    for row in sources:
        if not valid_url(row["url"]):
            raise ValueError(f"invalid or placeholder URL for {row['name']!r}")
        if row["internals_modified"].strip().lower() != "no":
            raise ValueError(f"external internals unexpectedly modified for {row['name']!r}")

    by_key = {row["cite_key"]: row for row in refs}
    expected_identifiers = {
        "ogita2005": "DOI: 10.1137/030601818",
        "niemetz2024": "DOI: 10.1007/978-3-031-65627-9_9",
        "zhang2025": "DOI: 10.1007/978-3-031-98682-6_12",
        "ieee2019": "DOI: 10.1109/IEEESTD.2019.8766229",
        "park2026": "DOI: 10.48550/arXiv.2601.17198",
        "gilot2026stainless": "DOI: 10.1007/978-3-032-22749-2_1",
        "gilot2026github": "DOI: 10.1145/3798203",
    }
    for key, identifier in expected_identifiers.items():
        if by_key.get(key, {}).get("persistent_identifier") != identifier:
            raise ValueError(f"unexpected identifier for {key}")

    same_venue = [
        row for row in sources
        if row["resource_type"] == "Information and Computation research article" and complete(row)
    ]
    influential = [
        row for row in sources
        if complete(row)
        and (
            row["resource_type"] in {"canonical research article", "influential research article"}
            or "influential calibration" in row["integration_mode"].lower()
        )
    ]
    adjacent = [
        row for row in sources
        if complete(row) and row["resource_type"].startswith("adjacent ")
    ]
    if len(same_venue) != 12:
        raise ValueError(f"expected 12 complete same-venue papers, found {len(same_venue)}")
    if len(influential) < 5:
        raise ValueError(f"expected at least 5 complete influential papers, found {len(influential)}")
    if len(adjacent) < 5:
        raise ValueError(f"expected at least 5 complete adjacent papers, found {len(adjacent)}")

    hubrecht = next((row for row in sources if row["name"] == "EFT code verification record"), None)
    hubrecht_status = "" if hubrecht is None else hubrecht["reading_status"].lower()
    if hubrecht is None or not any(token in hubrecht_status for token in
                                   ("unavailable", "blocked", "not directly inspected")):
        raise ValueError("newest-work access boundary is not explicitly retained")
    guide = next((row for row in sources if row["name"] == "Information and Computation Guide for Authors"), None)
    guide_status = "" if guide is None else guide["reading_status"].lower()
    if guide is None or not any(token in guide_status for token in
                                ("not read", "blocked", "complete guide remained")):
        raise ValueError("live venue-guide access boundary is not explicitly retained")

    result = {
        "status": "passed",
        "scope": "structural inventory and calibration audit; not a substitute for live metadata resolution or full-paper reading",
        "reference_entries": len(refs),
        "unique_cite_keys": len(set(keys)),
        "minimum_reference_target": 55,
        "frozen_reference_count": 59,
        "duplicate_identifiers": 0,
        "duplicate_titles": 0,
        "citation_context_rows": len(contexts),
        "citation_context_keys": len(set(context_keys)),
        "external_resource_records": len(sources),
        "complete_same_venue_papers": len(same_venue),
        "complete_influential_papers": len(influential),
        "complete_adjacent_papers": len(adjacent),
        "bounded_newest_work_records": 1,
        "unverified_live_guide_records": 1,
        "corrected_identifiers_checked": expected_identifiers,
    }
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "bibliography-audit.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
