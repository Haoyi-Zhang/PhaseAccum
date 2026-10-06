# Reference verification record

The final manuscript contains 59 BibTeX entries and cites all 59. The paper-side parser checks balanced BibTeX entries, every `\\cite` key, missing and unused keys, duplicate persistent identifiers, and selected high-risk identifiers. The artifact-side audit freezes the same 59-key inventory and the declared 12+5+5 reading-calibration records.

Identifier coverage is:

- 55 DOI-bearing entries;
- three arXiv records, one of which also has a DataCite DOI;
- one HAL record;
- one classic 1963 book without a persistent identifier.

No duplicate identifier or duplicate normalized title is retained. `reference_audit.csv` records the title, authors, publication, identifier, manuscript locations, and verification scope for every key. `external_resources.csv` separately records source access and full-paper calibration; a persistent identifier is not treated as proof that the full text was read.

The paper-side duplicate-identifier check reads DOI fields and identifier-bearing
annotations, notes, publication fields, and URLs, including nested arXiv and HAL
labels. Repeated spellings within one entry are not duplicate publications.
`paper/test_references.py` checks these cases with owned synthetic entries and
the current 59-entry bibliography; the paper build runs those tests before the
reference audit. These are parsing checks, not live source or full-text checks.

The 2026 direct-work records were rechecked against publisher, author, arXiv, ACM, Springer, conference, or HAL pages where accessible. The Hubrecht--Melquiond bibliographic record and ARITH 2026 program are public, but the HAL article body remained blocked by a human-verification page in the retained intake. The manuscript therefore makes only a bounded object-level comparison and no firstness, subsumption, or exhaustive-overlap claim.

The complete live Information and Computation Guide for Authors was likewise not directly inspectable in this environment. The 21-page length is an internal project constraint, not asserted as a publisher limit. Human authors must recheck live submission, authorship, disclosure, ethics, data, repository, and AI-use rules before external submission.
