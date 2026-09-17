# Audit and delivery permissions: production hold correction

## Problem

During the approved September 17 maintenance, live catalog comparison found that Supabase's `postgres` creator defaults grant ALL table privileges to `service_role`. The previous migration's narrower GRANT statements add permissions; they do not remove default grants. The service role could UPDATE, DELETE and TRUNCATE both event tables and DELETE/TRUNCATE the journal delivery ledger. Anonymous and authenticated roles remained denied on the new private tables.

The original isolated fixture granted narrower privileges and therefore missed this production behavior. The full catalog comparison caught it after PR #1 was merged and the two approved migrations installed. Production fingerprints still match the maintenance backup; no historical row was changed or relabeled. There is no evidence of an audit deletion, and the new discovery-event and delivery tables are empty.

## Correction

`20260917133500_restrict_audit_ledger_privileges.sql` is an additional migration. Do not edit or replay the two installed migrations.

- Reset public/anon/authenticated/service-role grants on the two audit tables; give `service_role` SELECT and INSERT only.
- Reset ledger grants; allow SELECT, INSERT and column UPDATE only for `status`, `verified_at`, `resolution_evidence`. Existing patches, source snapshots and delivery identity cannot be rewritten by the service role.
- Remove direct execution permission on the existing trigger functions. Audit triggers continue to insert under their invoking role; trigger behavior is tested.
- Preserve every row, RLS setting, constraint, index, global default privilege and strategy rule. No role, credential, execution flag or application behavior changes.

Database owners/administrators remain trusted privileged operators. This change constrains the application's service role; it does not prevent a database owner from changing grants or data. Manual ledger resolution remains an attributable operator procedure.

## Verification

All three migration suites passed independently:

```text
node tests/test_migration.mjs
node tests/test_live_schema.mjs
node tests/test_production_default_privileges.mjs
```

The new regression first proves DELETE is permitted after the old migration under broad creator defaults, then applies this correction twice. It verifies unchanged evidence, denied audit updates/deletes/truncates, protected ledger identities/snapshots/patches, working candidate/discovery triggers, rollback when audit insertion fails, PENDING uniqueness, successful VERIFIED completion, and resolution-evidence requirements. Every fixture is isolated infrastructure data.

A separate native PostgreSQL 17 rehearsal restored the fresh private production application archive into a new loopback-only database, used the actual `postgres` creator role and restored its default grants, and reproduced all nine live catalog sections (ACL item order normalized). The correction passed nine native checks: all rows preserved after repeated application, exact audit permissions, ledger column restrictions, no delete/truncate, working candidate/discovery triggers and writer completion, and complete rollback of local test mutations. No production test mutation or Google Sheet write occurred. Private archive/data/credentials are not in this repository.

## Production status and remaining gate

PR #1 merge: `ddc442ab53d38d3dbd7a67fc3ad1cfe8663718fd`. The Worker and Orchestrator deployed that commit before the hold; only the Worker's new health response was verified. Discovery and Consumer retain `edc71cd`. Both cron builds are unchanged, and the separate executor retains its original build. All seven resources are suspended with auto-deploy off.

This third migration is prepared and locally verified but **not applied to production**. Do not resume schedules or services merely because the earlier deployment was healthy. Obtain approval for this additional correction, verify current source/master/schema/backup state, apply through canonical migration history, and require effective permission checks (including forbidden operations) before completing the remaining health/deployment sequence. Keep every resource suspended afterward. Journal writer activation, market observations and paper execution remain separate work.

Strategy #1 v0.3, Experiment Plan v0.5 and execution-disabled Phase 1 SHADOW are unchanged. This follow-up does not certify live prospective behavior, writer credentials/scheduling, or broker-side state.
