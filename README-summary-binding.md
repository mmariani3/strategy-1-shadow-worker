# Citation references and summary timing (v25)

## Problem and resulting behavior

The [preserved v24 provider answer](README-nature-provider.md) remains rejected.
Two declarations repeated only part of the citations already recorded on their
economic assertions. A separate source review also found a forecast describing
late 2025, 2026 and beyond labeled `NOT_TEMPORAL` in a general summary clause.

Opt-in v25 removes the repeated citation lists from economic-nature declarations.
It binds each declaration to the whole original assertion or amount entry by its
index. The existing source-bearing fields keep their complete citations and
validation. The host does not guess missing citations or repair provider output.

Materiality summaries reference the complete economic terms, including forecast
timing and local qualifications. General summary clauses retain their existing
time bases and gain explicit role checks. A declared prospective or unresolved
assertion cannot remain in a general clause that lacks a compatible time basis.
Forecast economics belong in the referenced full terms; unresolved information
remains in the existing unresolved fields.

This is infrastructure consistency, not machine-verified source meaning.
[Structured Outputs can still contain mistakes](https://developers.openai.com/api/docs/guides/structured-outputs).
A false statement and an equally false role declaration can agree and pass these
checks. Full-source review remains required; no semantic acceptance is inferred.

## Finding / fix / evidence / limitation checklist

| Finding | Fix and changed files | Regression evidence | Remaining limitation |
| --- | --- | --- | --- |
| Duplicate citation lists disagree | `research_binding.py`: `TermReference` and `AmountReference` select existing original fields; no repeated citation property is accepted. | Reordered assertion arrays bind by term index, complete citations survive, duplicate/missing/out-of-range/boolean references reject, original source validation still runs. | Correctly bound citations may still fail to support the prose. |
| Forecast summary labeled atemporal | `research_binding.py`: complete `materiality_term_indices` links and per-clause `materiality_clause_roles`; declared forecast/unresolved scopes reject in general clauses, other scopes must match their bases. | Prospective `NOT_TEMPORAL` example rejects; linked terms preserve complete forecast meaning/timing/qualifications; all five previous general time bases remain representable. | Mutually consistent false prose/roles can pass. This is explicitly exercised and retained for source review. |
| New adapters could rewrite original history | `research_reviewer.py`, `review_attempts.py`, `evidence_review.py`: explicit new version only, complete request validation before reservation, no automatic retry. | Original text/envelope/wrapper retained; failed answer preserved; retry blocked; full historical replay. | v24 remains available with its original behavior and original rejection. |
| Review could show a derived answer instead of the original | `research_field_review.py`: restore exact v25 original after internal compatibility projection, add new summary contract items under `1.3.0-summary-binding-review`. | Exact original identity, immutable ledger, attributed decisions, deterministic review rendering and revision status checked. | Attributed review is not independent human acceptance; rendered mobile usability remains unverified. |

All new regressions are in `tests/test_research_binding.py`. They use synthetic
infrastructure fixtures and fake providers, excluded from Strategy #1 evidence.

## Contract

Implementation: `1.24.0-automated-research`; prompt: `governed-research-v25`.

- The full inherited draft, rule applications, term assertions and meaning
  contract remain. No source text, authority text, term, facet or qualification
  is removed from the provider input or original response record.
- Each `term_classifications.term_index` identifies the original assertion with
  that **term index**, regardless of array order. Each amount `entry_index`
  identifies its original entry. Terms and amounts must be covered exactly once.
- The v25 response excludes `core_passages` and amount-declaration `passages`.
  Only an internal validation projection derives them from the original fields.
  That projection is never presented as the provider's original response.
- `materiality_term_indices` includes each economic term once, retaining even
  unresolved terms. Resolved summary links contain the whole original term and
  assertion, preserving every timing, condition, qualification and source list.
- `materiality_clause_roles` covers every materiality-support clause once.
  `OCCURRED`, `PUBLICATION`, `ATEMPORAL`, `MARKET_OBSERVATION` and `CAPTURE` match
  their existing bases; capture metadata never establishes publication/event
  time. `PROSPECTIVE` and `UNRESOLVED` fail closed in this field placement.
- Core/amount nature consistency, original source validation, positive output
  limits and full-input/no-truncation checks remain. No keyword-based semantic
  validator or invented trading threshold is introduced.
- CLI default remains v20. v25 requires explicit preparation and an explicitly
  supplied provider; this change adds no automatic dispatch or credential access.

## Offline verification

**1,121 tests passed in 1,196.15 seconds**, including 43 new regressions. All
106 tested Python files retained their tested hashes throughout the full run.
The suite blocks HTTP requests to live services and uses local fixtures.

Test result manifest:
`414898254fdc5a1d4e8bb8653b4f85fcc0a6084e54fcda40d8511df3a443c1df`.

All **123 historical outcomes replay exactly: 60 research admissions / 63
rejections**, across 27 unchanged ledgers. The final prepared request is
153,663 bytes, with the unchanged 250,000-byte input and 12,000-output-token
limits. It has not been dispatched.

Historical replay manifest:
`35b5f5203c0938ed2a8c4ebe04c381232d017bbb4a8a812e230199c3dcba52a6`.
Prepared request:
`28e1c61f16aae44897e28636620bb1dacbf6e12da67ae492fa6b87d3fb67cd2d`.

All three current living-master revisions match the full texts bound to the
prepared request. Historical replay uses each historical request's original
authority, not current rules substituted into old records.

The offline example is explicitly `AUTHOR_ANNOTATION_NOT_PROVIDER_OUTPUT`.
It supplies a prospective role for the preserved v24 summary statement and
reproduces rejection. A separate structural example removes that duplicate
general clause while leaving the **entire economic inventory and all original
term assertions unchanged** and supplying references to all three terms. Both
annotations and the removed clause are retained separately from the original.
This demonstrates representation and validation, not actual model improvement.

The original v24 answer remains `NATURE_SOURCE_BINDING_MISMATCH`, with no new
completed assessment. Its reviewer records, original response and ledger retain
their hashes. The complete v23 report and attributed assessment regenerate
exactly. No old artifact is relabeled, repaired or overwritten.

Reproduce repository regressions with installed dependencies:

```text
python -m pytest -q tests/test_research_binding.py
python -m pytest -q
```

The existing read-only review CLI accepts completed v25 research records. A
rejected original still cannot be passed to the completed-assessment recorder.

## Boundaries and remaining evidence

**Zero paid API calls and no credential access in this offline step.** The
subsequent [bounded provider test and source review](README-binding-provider.md)
preserve the actual original answer and its separate judgments. Passing offline
cases does not establish general reliability, hands-off readiness, trading
eligibility or profitability.

No database migration is required. No Strategy v0.3 or Experiment v0.5
methodology, risk, setup, trigger, stop, target or eligibility change. No synced
source or Journal write, production configuration change, merge, deployment or
execution enablement. Phase 1 SHADOW and disabled broker execution remain
repository boundaries. **Live runtime configuration and live Journal state were
not verified.**
