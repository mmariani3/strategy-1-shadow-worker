# Tier references and readable source review — v19

The subsequent [provider comparison](README-tier-comparison.md) tested this
unchanged runtime. Both Fubo answers passed the schema/parser; source-content
defects remain. KDP was blocked by the full-input limit. The offline record below
retains its original scope and results.

The v18 provider comparison rejected one answer because it selected general
catalyst guidance alongside a tier-specific rule. New v19 requests restrict each
proposed tier to catalog rows carrying that same tier label. A separate local HTML
report makes source/prose inspection easier without filtering the evidence.

## Contract and boundaries

The default prepare-only CLI uses `1.18.0-automated-research` /
`governed-research-v19`. `research_tiers.py` derives A/B/C reference choices from
the supplied, validated Strategy Rules catalog. Nested schema branches require
at least one matching rule for a proposed tier. General guidance remains in the
full masters; it cannot be selected as a proposed-tier reference. A category with
no catalog rows is unavailable. UNRESOLVED remains available and never forces a
proposal. No rule numbers or new strategy categories are hardcoded.

Local validation repeats the restrictions and retains prior duplicate-reference,
event-fact, strict-type and evidence checks. The complete request is verified
before reservation. Original answer text passes unchanged through the frozen v18
parser with explicit v19 attribution. Historical v18 and earlier routes remain.

The host does not choose or approve a tier. A correctly labelled reference can
still be substantively wrong. Full source inputs, the single assessment scope,
economic inventory, 250,000-byte input ceiling and 12,000-token output limit in
the offline preparation remain unchanged. Oversize inputs fail without truncation.

The schema uses nested `anyOf`, constants and enums supported by the
[Structured Outputs guide](https://developers.openai.com/api/docs/guides/structured-outputs),
checked September 22, 2026 Pacific. **No v19 request has been sent to a provider.**
Actual schema acceptance and model compliance remain unverified.

## Readable offline review

```text
python research_review_view.py --packet packet.json --request request.json \
  --draft original-draft.json --reference reference.json \
  --report source-omissions.json --output reports
```

The CLI verifies the original omission report before generating an immutable,
self-contained HTML file. Open that file in a browser. It needs no server, account,
scripts or network access. The complete original JSON inputs are still required
for reproducible verification; preserve their original ordering and content.

- A queue links adjacent passages sharing source, path and citation status.
- Every passage remains visible, in order, with original text and offsets.
- Model statements appear alongside the passages they selected. Neighbor links
  expose continuations across group boundaries.
- Narrative-only selections, uncited text, full captured source, indexing gaps,
  externally authored reference expectations and the full original answer remain.
- Record identity includes the original run/candidate/signal/journal-trade trace,
  request/draft/reference/report digests and a separate view identity.
- Untrusted text is HTML-escaped. The page has no executable content, external
  resources or forms, and a restrictive content security policy.

Grouping is for navigation. It does not rank importance, remove boilerplate,
prove an omission, create a materiality threshold or change the original admission.
Reference judgments retain their authorship. This display is not an independent
reviewer and does not store new judgments. Use the existing attributed completeness
review workflow for recorded assessments.

## Verification and finding checklist

**876 tests passed in 98.97 seconds**, including 29 new regressions, using
`PYTHONPATH=.deps python -m pytest -q`. No provider calls or credential access.

| Finding | Fix / changed files | Test and replay evidence | Remaining limit |
| --- | --- | --- | --- |
| Proposed tier could select general or wrong-tier rules | `research_tiers.py`; explicit routing in `research_reviewer.py`, `review_attempts.py`, `evidence_review.py`, `run_research_reviewer.py` | A/B/C matching references accepted for research only; wrong/general/unknown/empty references rejected; request tampering rejected before reservation | Real v19 provider behavior untested; reference labels cannot prove meaning |
| Rule numbers could become stale | Choices derived from governing catalog; no hardcoded IDs | Moved categories and absent tier catalog tests; exact schema/catalog comparison | Governing text must still be interpretable by the existing catalog builder |
| Source flags were cumbersome to inspect | `research_review_view.py` verifies and groups existing reports | Every row, full source, narrative-only citation and indexing gap retained; markup and changed-evidence regressions; browser inspection of heading, navigation and source/prose columns | Long reports still require attributed source review; mobile and hosted workflows not verified |
| Historical evidence could be rewritten | Frozen version routes; `research_reference_coverage.py`, `research_completeness_review.py`; historical CLI test pins v18 | All 113 outcomes replay exactly: 52 research admissions, 61 rejections; all 20 ledger hashes and saved artifact hashes unchanged; 32 historical audit/review records exact | Old rejections remain rejected; replay is not new model evidence |
| New schema could reduce evidence input | Complete input and master binding retained | 16 full requests prepared and validated, 156,880–244,685 bytes; none sent or truncated | Future larger sources may exceed the ceiling |

Regression files: `tests/test_research_tiers.py`,
`tests/test_research_review_view.py`, and the historical default fixture in
`tests/test_research_typed.py`.

Four HTML files were generated and exactly verified from the original VRNA/BNTX
answers. Both VRNA pages retain 188 passages; both BNTX pages retain 132. Navigation
groups number 33/33/20/25 respectively. These are location counts, not defect counts.
The original VRNA GPT-5.5 `[71,75]` selection remains rejected and is not repaired.

Private replay manifest:
`f262ed4b8a009fd11b5818b69e7d65d0a174cbf0b9ae16bef1ee89e63625379b`.
Private `tier-offline-20260922` artifacts retain prepared requests, review pages,
fresh master revision checks and hashes. Raw sources, private masters and responses
are not published in this PR. The [earlier paid comparison](README-typed-comparison.md)
retains its original findings and cost; this v19 step cost **$0 in API usage**.

## Rollout status

No migration, production deployment, Journal write, strategy observation, synced
reference edit or broker enablement. Living Strategy v0.3, Experiment v0.5 and
Automation v0.4 revisions were reread and matched the complete stored masters.
No methodology, risk or observation-eligibility change. Phase 1 SHADOW and broker
execution disabled remain repository boundaries. Live runtime configuration,
production dispatch and Journal state were not checked in this offline step.

Neither model is approved for unattended qualification. Remaining work is actual
v19 provider compatibility/compliance and attributed semantic assessment against
fresh, frozen source references. Any paid comparison needs its own explicit budget;
development replays do not constitute independent or held-out acceptance.
