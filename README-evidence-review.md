# Source-bound research review and session reports

Status: **research-only infrastructure**. Stacked on the hands-off operations change in PR #4.

This package captures the entire finalized discovery funnel, retains original source records and actual downstream IDs, validates cited draft assessments, and writes immutable local research artifacts. It has no candidate-promotion, Worker, Journal, broker, notification or model-provider client. It is not an accepted autonomous qualitative reviewer.

Strategy #1 remains v0.3, Experiment Plan v0.5, and the governing Automation Specification v0.4. No living master or synced source is changed. This package adds no migration, dependency, hosted service or subscription.

## Run

Use the repository's existing Python dependencies. Read the three living masters through an authorized connection before capture; create a private JSON authority manifest with exactly these entries:

```json
{
  "strategy": {"document_id": "1DBtZYKLV0MdIg_f8NspwVLIoeTxCi9amlRFHO9Ji0tM", "version": "v0.3", "revision_id": "ACTUAL_LIVE_REVISION", "read_at": "ACTUAL_ISO_TIMESTAMP_WITH_TIMEZONE"},
  "experiment": {"document_id": "1sfL2FAn-p6peY8LLbEwka_2gYIGiGka_BGe6prsygCc", "version": "v0.5", "revision_id": "ACTUAL_LIVE_REVISION", "read_at": "ACTUAL_ISO_TIMESTAMP_WITH_TIMEZONE"},
  "automation": {"document_id": "1uDGbnHQHX6tDD9a5efJD-O9FuMW6xvn_xlhCrltlfjw", "version": "v0.4", "revision_id": "ACTUAL_LIVE_REVISION", "read_at": "ACTUAL_ISO_TIMESTAMP_WITH_TIMEZONE"}
}
```

Provide a private, SELECT-only database connection through `REVIEW_DATABASE_URL`. Require certificate verification for remote connections. Do not put credentials in command arguments, committed files or logs. The connection must permit reads of discovery runs/items, candidates and signals; hosted identity provisioning is outside this change.

```text
python evidence_pipeline.py --run-id RUN_UUID --authorities PRIVATE_MANIFEST.json --output PRIVATE_OUTPUT_DIRECTORY
```

The loader uses a repeatable-read, read-only transaction. It reads a finalized run, all its discovery items, linked candidates and each candidate's referenced latest signal. It does not re-run discovery, fetch articles, request quotes, inspect live Sheet state or change any operational state. It captures the current database snapshot, not the complete historical event ledger.

Offline review of a captured snapshot:

```text
python evidence_pipeline.py --snapshot PRIVATE_SNAPSHOT.json --authorities PRIVATE_MANIFEST.json --output PRIVATE_OUTPUT_DIRECTORY
```

Snapshot shape: `{run, items, candidates, signals, captured_at}` using the actual database row columns and timezone-aware capture time. Missing arrays of candidates/signals default empty; referenced downstream records must be present. The manifest's read times must be at or before capture. For a historical snapshot, preserve its original authority manifest; re-reading a master later must not be falsely backdated. A new research capture may incorporate the historical records with a new truthful capture time.

By default every criterion is `UNRESOLVED`, explicitly attributed to `evidence-packet-builder`, model `none`. This means no substantive reviewer ran. For testing a separately prepared draft, `--responses PRIVATE_RESPONSES.json` accepts a map of packet ID to the exact schema in `request-PACKET_ID.json`. Absent responses remain unresolved; malformed supplied responses fail closed. Supplying a response does not make it an accepted live review.

## Artifacts and integrity

- `packet-*.json`: original run/item records (including macro evidence and rejections), captured news/filings/mover data, existing reviews and referenced candidate/signal records. Includes governing identities/revisions, timestamp meanings, source state, missing inputs and actual run/item/candidate/signal/journal IDs. Missing downstream IDs stay null.
- `request-*.json`: research-only instructions, all required assessment topics, strict JSON response schema and the untrusted packet. It does **not** contain the living master text. A future authorized reviewer must receive that text separately; document IDs alone are insufficient instructions.
- `review-*.json`: attributable draft with implementation, model and prompt versions, original source spans and a structural-validation result. Even all-SUPPORTED drafts remain `eligible_for_handoff=false` and `semantic_verification=NOT_ESTABLISHED`.
- `bundle-*.json`: all packets/reviews for the run, source digest and capture time.
- `summary-*.json/.md`: deduplicated source counts, unresolved-review blockers, infrastructure exclusions and explicit unknown opportunity outcome. The report makes no live Journal reconciliation claim.

Hashes identify exact content; they are not signatures or proof of factual truth. A matching quote proves only that text occurred in the captured source, not that it supports a conclusion. Publisher timestamps do not establish underlying event freshness. Same-symbol articles/filings do not establish same-event verification or independence. Existing approvals are evidence of a prior review, never refreshed approvals.

Identical artifacts can be saved again without overwriting. Changed inputs/reviews receive new IDs; conflicting duplicate run snapshots are rejected by the summary. An interrupted local file write can leave an incomplete file; retry then refuses to overwrite it. Retain that file for diagnosis and use a new output directory. This is not crash-durable hosted object storage, a distributed job ledger or a notification-delivery guarantee. Protect local artifacts with appropriate access controls; they contain source and strategy records.

The summary's `UNKNOWN` result is deliberate even for a zero-item run: this package cannot establish full-session prospective observation. It must not start or complete an experimental assessment session or count an executed trade.

## Tests

```text
python -m pytest -q
python tests/native_evidence_acceptance.py --connection-file PRIVATE_LOOPBACK_CONNECTION.json --template-db writer_acceptance_TEMPLATE
```

The native acceptance test clones an existing loopback-only writer-acceptance database into a fresh `evidence_acceptance_*` database. It inserts two explicit INFRASTRUCTURE_TEST discovery items there, proves PostgreSQL rejects writes from the snapshot transaction, and verifies repeatable reads during a concurrent fixture update. It makes no external HTTP, Sheet or broker calls. Retained isolated databases/artifacts are for inspection; no production fixture is created.

Regression coverage includes full-funnel integrity, duplicate/missing lineage, source/authority mismatch, malformed responses, exact citation checks, timestamps, rejected records, source prompt-injection text remaining data, no automatic handoff, infrastructure exclusions and immutable repeated saves.

## Remaining activation work

See [the proposed review-method acceptance plan](REVIEW-METHOD-PROPOSAL.md). Automated source retrieval, current market measurements, a real attributable reviewer, independent semantic assessment, prospective revalidation, accepted implementation policy, hosted identities/storage and exception-only reporting remain unimplemented or unverified. No production process should consume these drafts as approvals.
