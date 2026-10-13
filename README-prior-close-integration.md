# Dated prior-session evidence integration

Snapshot `prevDailyBar` can point at an older session during premarket. The new
collector requests raw SIP daily bars for the calendar-derived previous session
across the exact active, non-OTC universe collected by the activity adapter.
It preserves the original snapshot dates, missing-close reasons and gap fields.
An available historical raw close remains review-required; it is not a verified
corporate-action-adjusted reference or an official auction-close assertion.

`premarket_evidence_collection.collect_premarket_with_prior` returns:

- `items`: the existing activity subset with a separate dated evidence attachment.
- `universe_items`: every requested symbol, including no-activity and unprocessed
  symbols. These are coverage records, not qualified candidates.
- `integration`: separate completion, prior-close availability and missing-reason
  counts. Both collectors must agree on the prior session.
- `collection`: original activity manifest plus dated source/window/page/batch
  coverage provenance. Original snapshot fields are never replaced.

The two collectors retain their individual 120-second and 120-page caps and
share a 180-second request budget. A late response is rejected. These are request
budgets, not process termination guarantees; hosted use requires a watchdog.

`premarket_evidence_storage.persist_universe` uses the existing discovery-item
JSON field, 100-row/1-MiB batches and a shared 180-second storage/readback budget.
All expected fields are hashed before writing; acknowledgements and paginated
readback must match. A timeout never authorizes a replay, even if later readback
finds all rows. Partial/ambiguous rows remain for independent reconciliation.
It requires explicit database callbacks, audit context and a caller deadline;
there is no implicit credential access or production destination.

The coordinator exposes a default-off `include_dated_prior_evidence` request
flag restricted to staging, PREMARKET, v0.3 and INFRASTRUCTURE_TEST before claiming
a run. It stores attached activity evidence and the coverage manifest. It does
not expand its news/SEC candidate loop to no-activity symbols or claim those
coverage-only rows were persisted. Deterministic run-key replay protection is
unchanged. The normal Strategy #1 path remains unchanged.

The separate `premarket_oct13_acceptance:app` exercises the full-universe storage
path. It has only health, authenticated preflight/result, and a single-minute
acceptance endpoint on October 13, 2026 at 06:00 Pacific. It atomically claims the
existing unique infrastructure run key before collection. Only the existing
staging service/database are accepted. Writes stop at 06:15 and the app expires
at 06:25. Every run remains PARTIAL/INFRASTRUCTURE_TEST. In this isolated test,
the legacy `candidates_discovered` field counts acknowledged coverage rows;
the manifest explicitly labels that count and separately records activity items.

This package is a deployment candidate, not hosted acceptance proof. Deployment,
authenticated rehearsal, independent readback/cleanup, fresh launch checks and
arming must succeed separately. No scheduled invocation is created by importing
these modules. No journal, qualification, promotion, monitoring or order path is
added to the isolated app. Passing it does not accept the full discovery protocol
or approve automated qualitative setup decisions.

Tests use invented offline fixtures, including a 13,240-symbol universe, and
block live HTTP. Those fixtures never enter Strategy #1 evidence.
