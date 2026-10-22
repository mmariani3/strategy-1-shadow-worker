# Connector snapshot bridge — no-scan scope

The no-scan rehearsal now supports two explicitly distinct preservation methods:
the existing complete-row DB-API collector and a fixed Supabase connector query
that hashes every row of all eight protected tables. The new format is
`NO_SCAN_FULL_TABLE_FINGERPRINT_V1`. It never masquerades as exported rows and
cannot feed the normal discovery acceptance readback, which still requires
detailed row evidence.

`coordinator_connector_snapshot.sql` performs one read-only repeatable-read
transaction, with canonical timezone/format settings, a 30-second statement
timeout, RLS filtering disabled (restricted visibility raises an error), and
an explicit privileged-role/visibility check in the response validator. It
returns complete counts and SHA256 digests, catalog metadata and audit-function
hashes, transaction timestamps/snapshot identity, exact test-key/unfinished-run
counts, and caller information. No application row payloads are returned.
Missing tables, incomplete/truncated responses, installed pg_cron requiring
further review, incorrect request nonce, stale times or unexpected caller/run
state fail closed. At most 100,000 rows and a 2 MiB response are accepted.

The authenticated host invokes `supabase_execute_sql` with the hardcoded staging
project ID. Database name `postgres`, query nonce and project strings are not
authentication proof by themselves. The connector's authenticated request target
establishes destination. No credential store is opened by this bridge.

`coordinator_connector_mailbox.py` connects the desktop Python process to that
host tool. The host reconstructs the pinned SQL; it never runs SQL taken from a
request file. Requests carry only day, nonce, fixed project, expiry and query
hash. An exclusive host claim prevents retry after an ambiguous tool call.
The relay waits at most 45 seconds; the collector rejects responses taking over
60 seconds. These bounds do not cancel an already dispatched remote query:
the server statement timeout and cleanup owner remain necessary safeguards.
The request directory must be unique and access-controlled; a nonce is not a
substitute for filesystem permissions or host authentication.

The rehearsal compares the tagged baseline and schema hash before/after. The
original scan controller still uses full rows. Both Python modules and the SQL
template are now in the pinned source manifest; old manifests cannot authorize
this changed package.

The cleanup path also now polls an asynchronous database pause, with one pause
request and bounded status reads until the existing T0+8-minute deadline.
It does not extend the window, stop the watchdog before verified cleanup, or
convert a pending/failed pause into success.

## Verification and remaining gates

- 786 application/controller/bridge tests passed, including actual file-relay
  exchange with an offline host callback, stale/truncated response rejection,
  no-scan controller integration, changed-record/schema failure, asynchronous
  pause success and timeout/error cleanup behavior.
- Eight additional in-memory PostgreSQL checks executed the generated query.
  All 5,001 fixture rows were covered; a last-row field change, inserted row,
  RLS change and missing table were detected. Local engine is PostgreSQL 18.3;
  staging is PostgreSQL 17. Multi-connection concurrency was not simulated.
- Authenticated staging proof, if completed, is recorded separately in
  `../tooling/coordinator-connector-hosted-result-2026-10-15.json`; the tests above
  alone are not hosted proof. A successful database-only check does not validate
  application preflight authentication, deployment, watchdog or notifications.
- The hosted application still needs reviewed publication and its own deployment
  shutdown guard. No publication/deployment or service activation is included
  in this bridge implementation.
- Notification requirements are unchanged: missing run, stalled run, first and
  second consecutive failure, and cleanup failure each need distinct
  recipient-confirmed receipt evidence. Send acceptance alone is insufficient.
  No messages are sent by this bridge or no-scan rehearsal. Unattended discovery
  stays unarmed while these safeguards are unverified.
- A concrete rehearsal still needs current living-master revisions, caller
  inventory, exact deployed code/entry point, a dated bounded permit, current
  credential-use authority, verified evidence-directory access and an available
  cleanup operator. Expired October 13 credential permission is not reused.

This is infrastructure work only. Phase 1 SHADOW, disabled execution,
infrastructure-test exclusion, review-required candidate rules and validation
methodology are unchanged. Production schedules and weekday oversight remain
paused pending their governing acceptance gates.
