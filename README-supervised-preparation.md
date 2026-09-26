# Supervised preparation, with human decisions

Version 1.1 adds optional source-bound catalyst briefs and twelve saveable review questions.

## Catalyst briefs and review notes

Optional authored briefs separate event facts, management forecasts, economic
interpretation, timing, contrary evidence, limitations and proposed tier. Exact source
passages and author source-check notes are expandable. Proposed tiers never qualify a
candidate. The page displays attribution, actual review time and that independent
acceptance/current approval are not established.

Add `--briefs briefs.json` to the command below for a JSON list conforming to
`catalyst_brief.Brief`. Start from a preparation without briefs to obtain its identities.
Briefs must bind the same packet, symbol, complete trace, classification and snapshot
digest. Exact citation offsets must reproduce the supplied excerpt in a captured source
record's string field. Every claim must be displayed in the five required sections.
Authorship/check times must follow capture and not exceed preparation time. Unknown
fields (including approval flags), bad lineage, missing passages and duplicates reject.
The full funnel is retained and missing briefs remain explicitly absent.

The twelve questions accept Supported, Unclear or Fails with a reason/evidence reference,
or Unanswered. Review downloads bind packet, brief, preparation and source identities.
No risk calculation is needed to save review notes. Changing candidates clears answers.
Notes never become CurrentReview approvals, trigger confirmations, signals or orders.

This validates structure and source locations, **not truth, source independence,
authenticity of a claimed reviewer identity or semantic completeness**. A false inference
can cite a real passage; that limitation is explicitly tested. This first version accepts
only attributed author source checks. No model call is made by the page generator.
Historical examples stay outside prospective Strategy #1 evidence.

### Version 1.1 validation

- 162 focused Python tests passed across catalyst-brief, preparation, code-review,
  evidence-review and Journal modules. Covered attribution/chronology, source binding,
  missing claims, unsafe links, untrusted HTML, history and unchanged no-execution limits.
- Nine JavaScript tests passed, including simulated-DOM event handling: review downloads
  retain the correct candidate/brief identity; unanswered questions remain unanswered;
  changing candidates clears answers; answered questions without reasons block download.
- The historical ADMA example has nine source-linked claims, twelve unanswered questions,
  INFRASTRUCTURE_TEST classification, zero Journal rows and no prices or simulated fills.
  The preserved source body hash and extracted text were verified before use. The brief's
  source check was performed by its author, not an independent reviewer. Same-event
  independent corroboration remains explicitly unresolved.
- The browser was unavailable during version 1.1 acceptance. Visual layout and actual
  browser filesystem downloads remain unverified; simulated-DOM checks are not browser
  acceptance. Earlier browser observations below apply only to version 1.0.

Run `python -m pytest -q tests/test_catalyst_brief.py tests/test_supervised_preparation.py tests/test_code_review.py tests/test_evidence_review.py tests/test_journal.py`
and `node --test tests/test_supervised_preparation.cjs`. Initial sandbox runs hit Windows
temporary-folder/subprocess restrictions; the approved outside-sandbox reruns passed.

No paid model call, deployment, service resume, Journal write, strategy/master change or
broker action occurred. The three living-master revisions were rechecked and unchanged.

This adds an on-demand local preparation page around the existing discovery snapshot,
source checks and process-Journal projections. It replaces repetitive compilation and
risk arithmetic with one command. It is not unattended trading or a new strategy evaluator.

## What the operator receives

- Every discovered record, including rejections, plus scan/macro context. Search changes
  visibility only; it does not drop records or rank opportunities.
- A research digest of captured headlines and publisher summaries, reproduced verbatim,
  beside expandable complete source records, timestamp semantics and unresolved checks.
  This is deterministic source organization, not a newly generated AI assessment.
- A calculator for human-selected direction, entry, structural stop, target, risk budget
  and supplied daily counters. Exact fixed-decimal arithmetic enforces the existing v0.3
  $50 risk, $10,000 notional, $100 daily-loss and three-trade ceilings; quantities are
  whole shares. Below 1.5R is blocked; 1.5–below 2R flags the existing clean-structure
  review requirement. None of these calculations establish target/setup validity.
- Local, explicitly unapproved planning-draft downloads with source classification,
  trace IDs, source/capture time, entered-by identity, notes and implementation attribution.
  Changing inputs invalidates a calculation. Changing the candidate clears its plan.
- Draft Scan Coverage and Premarket Candidates records produced by the existing projector.
  There are no executed-trade records, Sheet patches against a live grid or broker requests.
  Infrastructure fixtures have no production Journal projection at all.

## Run

Use the repository's Python dependencies from `requirements-dev.txt`.

```text
python supervised_preparation.py --snapshot source-snapshot.json --authorities authorities-at-capture.json --authority-checks current-authority-checks.json --output .tmp/preparation
```

Open the returned `index.html` in a modern browser. It is self-contained, supports mobile
widths and makes no network requests. Nothing is saved automatically. Confirm a requested
download actually appears in the browser's chosen destination. Browser file delivery is
not a durable audit database; downloaded drafts require subsequent review and retention.

An existing finalized run can instead be read with `--run-id <UUID>` and the existing
private `REVIEW_DATABASE_URL`. This uses `evidence_pipeline.load_snapshot`: a repeatable-read,
read-only transaction. It never launches discovery, changes the database or resumes a service.
Only use an approved read identity. No credentials are embedded in output.

Both authority files map `strategy`, `experiment` and `automation` to `document_id`,
`version`, `revision_id` and timezone-aware `read_at`. The capture references must be valid
at capture; revision rechecks must correspond to an explicit read of the living masters.
The command validates these supplied references, not their provenance through a new Google
request. It refuses changed revisions and pins the reviewed Strategy revision for the
calculator. A new revision requires explicit re-review of this implementation.

For reproducible replay, `--prepared-at` fixes generation time. It is never a freshness
approval. Source timestamps are not replaced with generation time. Previous-session input
is labeled HISTORICAL_REPLAY; same-session input is still CAPTURED_SNAPSHOT_NOT_LIVE.
Reopening any saved page cannot refresh its evidence, approvals or source availability.

The source snapshot uses the existing evidence pipeline contract: `run`, complete `items`,
linked `candidates`, linked `signals`, and `captured_at`. Missing/duplicate/mismatched lineage
or an incomplete captured funnel fails closed. An honestly PARTIAL discovery run may be
displayed, but must contain all records declared by that run; incomplete coverage stays visible.

Outputs are content-addressed and exclusively created. Exact retries preserve files; modified
or interrupted/conflicting artifacts are not overwritten. Actual source/module hashes are
recorded. Full evidence stays available behind the digest, not silently shortened for display.

## Human and production boundary

Humans still review catalyst meaning, instrument eligibility, market/data quality, setup,
target, prospective confirmation, account state and position supervision. The page never
creates CurrentReview approvals, confirms triggers, calls the Worker or promotes candidates.
It does not establish that qualitative review policy or an execution route has been accepted.
Historical Worker decisions remain captured evidence only; missing signal/trade IDs stay null.

The Journal package is a draft, with `live_sheet_read=false`. Before any real delivery, use
the approved writer's fresh live read, stable-ID reconciliation, lock and verified readback.
Do not upload this package as an execution queue. Signal Queue remains legacy.

The tested automation is **on demand**, not a scheduled daily service. Fresh discovery/data
access, a chosen session, user chart access, execution-route acceptance, hosting and notification
delivery remain separate readiness work. No new API cost is needed to assemble this page;
new source collection or model research would be separate work. Browser controls do not imply
availability of current prices or consolidated market data.

Strategy v0.3 / Experiment v0.5 methodology and observation eligibility are unchanged.
Automated execution remains Phase 1 SHADOW and disabled. No production deployment, service
resume, schema migration, paid call, live Sheet write or broker operation is part of this change.

## Original version 1.0 verification

```text
python -m pytest -q tests/test_supervised_preparation.py tests/test_code_review.py tests/test_evidence_review.py tests/test_journal.py
node --test tests/test_supervised_preparation.cjs
```

- 135 focused Python tests passed, including 18 preparation cases: complete/empty funnels,
  infrastructure exclusion, source times, changed authorities, linked IDs, rejections, HTML
  injection, immutable retry history, draft-only projection and offline CLI operation.
- Six JavaScript tests passed: long/short geometry, exact decimal boundaries, notional/risk
  caps, daily limits, invalid/missing inputs, clean-structure flag and classified traceable drafts.
- Browser walkthrough used only an isolated INFRASTRUCTURE_TEST fixture. Verified calculation,
  recalculation after input edits, daily-loss suppression, clearing a changed candidate and
  filtering without dropping records. Download request feedback appeared; the browser's final
  filesystem save location was not independently verified.
- Historical read-only replay retained all 112 September 18 source records and produced 113
  draft process records, zero executed records and zero model/external writes. This is not a
  current scan, an independent strategy review or evidence of live deployment readiness.

Only additive files are changed. Existing Worker, executor, discovery, evidence and writer
implementations are not modified. Focused dependency regressions were run; the complete
unrelated provider-test suite was not rerun for this additive UI package.

This is a stacked draft on the existing research branch (#9); main and production remain unchanged.
