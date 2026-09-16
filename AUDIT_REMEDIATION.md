# Phase 1 audit remediation

Base: `edc71cd162078b165f13aaf34262ba6b377520b7` (GitHub main checked again September 16, 2026). This change fixes infrastructure and enforcement gaps. Deployment and test writes were limited to separately authorized staging; production SQL, services, orders, live Journal, and historical records were not changed.

Follow-up acceptance results and rollout checklist: [ACCEPTANCE_REPORT.md](ACCEPTANCE_REPORT.md). Acceptance found and fixed a discovery-state constraint mismatch, Scan Coverage dropdown mismatch, Decimal JSON encoding, and legacy Supabase server-key authentication. Apply **both** checked-in migrations in filename order. Native database/Google writer acceptance, real local HTTP lifecycle integration, and bounded hosted transport/RLS/infrastructure-exclusion checks passed. Hosted real-market behavior and journal scheduling remain unverified.

Authority reviewed: living [Strategy Rules v0.3](https://docs.google.com/document/d/1DBtZYKLV0MdIg_f8NspwVLIoeTxCi9amlRFHO9Ji0tM/edit), [Experiment Plan v0.5](https://docs.google.com/document/d/1sfL2FAn-p6peY8LLbEwka_2gYIGiGka_BGe6prsygCc/edit), and [Automation Specification v0.4](https://docs.google.com/document/d/1uDGbnHQHX6tDD9a5efJD-O9FuMW6xvn_xlhCrltlfjw/edit). These masters retain their respective authority. No source files are edited.

## Finding checklist

| Finding | Correction and files | Regression evidence |
| --- | --- | --- |
| 1. Target bypass | `main.py` requires target approval before both genuine trigger wait and confirmed TRADE. | `test_worker.py`: missing/false approval with both trigger states. |
| 2. Stale approvals and old confirmation | `review_contract.py`, `orchestrator.py`: explicit current review bound to snapshot, session and validity interval; new review ID; omitted current assessments are cleared. Price observations cannot renew approvals. | Expired review, prior session, mismatched snapshot, old confirmation, omitted liquidity/consolidation approval, and monitor expiry tests. |
| 3. Incomplete setup handoff | `discovery_coordinator.py`: timestamp, quality, current review, attribution; missing inputs or required clean-structure assessment hold readiness. Separate qualification/setup retained; legacy combined route retired. | `test_discovery.py`: accepted data fields, missing fields, lower-RR completeness, handoff trace, legacy route. |
| 4. Negative confirmation loses updates | `orchestrator.py` persists and evaluates full negative review. | `test_lifecycle.py`: missed trigger, failed liquidity, changed market context. |
| 5. Monitoring cannot resume | Explicit `resume_monitoring` review may supersede active observation; atomic audit retains before/after. Monitoring still only observes price crossings. | Resume, missing unmissed assessment, observed-only monitor, positive confirmation prerequisites. |
| 6. Journal planner only | `journal_writer.py`, `journal_projection.py`: live reads, stable IDs, writes, readback, advisory lock and durable delivery barrier; full discovery funnel, including pre-signal rejections. Signal Queue remains legacy and is not written. | `test_journal.py`: retries, concurrency guard, duplicate IDs, historical unkeyed conflicts, changed Sheet, lost reply/readback failure, multiple insertions, pre-signal funnel. |
| 7. Incomplete trace | Structured run/candidate IDs through setup and Worker inputs; signal primary ID and journal ID retained. Migration atomically logs candidate and discovery transitions with timestamps, states, reason, owner, version and review attribution. | Worker trace persistence, discovery attribution, handoff class conflict; real SQL trigger/rollback checks. |
| 8. Test evidence and version attribution | Explicit class/data kind; mislabeled tests cannot persist; infrastructure cannot enter strategy Journal. `build_info.py` records component version, available Git revision and source fingerprint; obsolete Worker override removed. | Classification/persistence guards, infrastructure exclusion, fingerprint and SHADOW assertions. |

## Current review contract

`CurrentReview` carries a unique `review_id`, nonblank `reviewer` and `evidence`, timezone-aware `data_timestamp`, `reviewed_at`, `valid_until`, and explicit true judgments for `data_current`, `catalyst_current`, `qualification_current`, `risk_current`, and `setup_current`.

The reviewer must actually refresh or revalidate these inputs under the governing masters. A new UUID or timestamp alone is not evidence. There is **no default freshness lifetime or new strategy threshold**. If the responsible reviewer cannot justify currency and a validity interval, leave the review unresolved: the Worker holds. The code verifies attribution and consistency, not the truth of a human assessment.

The snapshot timestamp must match the review; data <= review <= current server time < valid-until, within the candidate's New York session date. A confirmed signal must use that snapshot and review ID. Re-evaluation/confirmation requires a new review and all current assessments; omitted values invalidate previous approval. This includes daily risk/trade counts, target approval, market context and liquidity. Conditional consolidated-data and clean-structure approvals cannot silently carry forward.

`POST /items/{id}/qualify` requires reviewer and review time independently of setup. `POST /items/{id}/setup` accepts data timestamp/quality and the current review. Unresolved setups can be retained and routed for a HOLD; they are not advertised as ready. `POST /items/{id}/reject` records an attributable rejection before routing. `/promote` returns 410 for valid legacy requests; migrate callers to the separate contracts.

`POST /candidates/{id}/confirm-trigger` with `confirmed=false` still processes all supplied context. With `resume_monitoring=true`, the review must explicitly establish an unmissed, still-valid setup. Only a successful Worker evaluation restores WAITING_FOR_TRIGGER. Prior observations remain in immutable audit snapshots. A crossing by itself never confirms a trigger. Closed/terminal candidates cannot be resurrected.

Direct Worker callers must provide `candidate_id`, `experiment_class`, and `data_kind`; session/review are required to reach a valid signal. Discovery-linked ingestion checks run classification, symbol, qualification and predefined setup. Historical inputs lacking new evidence fail closed instead of being backfilled by inference.

## Migration and tests

The CLI-generated additive migration is `supabase/migrations/20260915234523_shadow_audit_remediation.sql`. It targets the existing Phase 1 database, including its candidate/event/signal tables and uniqueness constraints. It is **not a bootstrap schema**. It adds current-review and trace fields, atomic audit triggers, discovery events, and the journal-delivery ledger; no historical row is updated. Existing one-candidate-per-discovery-item and one-TRADE-per-journal-ID constraints remain required. Audit insert failure rolls back the state mutation.

Before any separately authorized rollout, inspect the target schema/roles and existing indexes against this prerequisite, apply the migration to an isolated copy, then run service/Sheets acceptance checks. The migration uses the Supabase backend `service_role` and its BYPASSRLS behavior; anonymous/authenticated roles receive no new access. A custom direct database writer role needs reviewed least-privilege grants. Do not use a transaction pooler for the session advisory lock.

Reproduce locally with Python 3.11+ and Node 20+:

```text
python -m pip install -r requirements-dev.txt
python -m pytest -q
npm ci
npm run test:migration
```

Python tests block requests-based network access and use in-memory fixtures. They deliberately exercise both evidence classes locally; they do not send synthetic STRATEGY_1 fixtures to production. The PGlite test runs the actual migration against a minimal existing-schema fixture and checks historical preservation, atomic audit rollback, role restrictions, and pending-delivery uniqueness. It does not prove compatibility with every live constraint/extension or replace staging integration testing.

## Journal writer operation

The standalone writer replaces the caller-snapshot patch planner; `/journal/reconcile` is removed. It is not installed as a scheduled production job. Install `requirements-journal.txt`, provide Google Application Default Credentials with access to the Sheet and `JOURNAL_DATABASE_URL` for a direct or session-pooled database connection. `JOURNAL_SPREADSHEET_ID` can point at an isolated test copy. Do not run acceptance fixtures against the live Journal.

```text
python journal_writer.py --run-id <UUID>
python journal_writer.py --candidate-id <UUID>
```

These commands are dry runs. Discovery-linked candidates require the complete `--run-id` path. A write requires both `--apply` and `JOURNAL_WRITES_ENABLED=true`, to be configured only in a separately authorized rollout. The writer covers Premarket Candidates and Scan Coverage, including discovery/watchlist/rejection records before any signal. It never writes Trade Journal or Signal Queue, and never treats a shadow signal as an execution. Infrastructure/unclassified runs and non-market candidates are rejected from strategy-journal delivery.

For each delivery it holds a database session lock, reads and locks source rows, reads the complete allowed Sheet grids, rejects duplicate/missing/conflicting identities, computes cell patches, rereads before writing, persists PENDING, writes once, reads back and reconciles, then records VERIFIED. Retries after success are NOOP. A lost reply, partial write, failed readback or process death after PENDING leaves a durable block. The database enforces one unresolved delivery per Sheet. The ledger retains source rows and structured trace alongside exact patches. Existing user Notes and unrelated columns are preserved.

**Pending-delivery recovery:** do not delete or automatically clear the barrier. Inspect its stored patches/source trace, read the current live Sheet, and reconcile each stable ID. Under the same writer lock, an authorized operator must document the observed cells, resolution, reviewer and timestamp in `resolution_evidence` before marking RESOLVED_MANUALLY. Then start a new dry run from fresh reads. This release intentionally has no automatic replay or repair command.

All automated writers must use this lock/ledger. Google Sheets offers no transaction spanning the database and other Sheet editors: a human or unrelated writer can still race after the pre-write read. Deployment requires a single approved automation writer and coordinated manual edits. The writer also stops at missing headers, full grids, oversized grids, duplicate IDs or matching historical rows lacking IDs; it does not guess or insert extra columns.

## Verified boundaries and remaining limitations

- Local code/tests verify SHADOW records and an unconditional disabled broker-submission flag even if the environment says true. No production configuration was changed or verified by these tests.
- Current risk defaults, approved setups/triggers, stops/targets, v0.3 ruleset and v0.5 experimental methodology remain unchanged. Runtime environment overrides still require independent verification.
- Production deployed revisions and configured risk limits were inspected read-only. Credentialed writer acceptance uses a test Sheet and local native database; hosted acceptance uses an isolated Supabase project and three staging services. Production migration deployment, loaded-process settings, writer scheduling, and real-market end-to-end behavior remain unverified. This PR is not production activation approval.
- Historical synthetic A/C records and old version labels remain untouched. Downstream historical analysis must consult the audit and explicitly reconcile exclusions; this change does not retroactively certify or relabel them.
- The writer synchronizes current process state; immutable database transitions preserve the detailed history. Existing blank or ambiguous historical trace requires explicit reconciliation, not automatic backfill.
