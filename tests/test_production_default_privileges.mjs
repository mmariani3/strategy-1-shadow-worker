// Local infrastructure fixtures only. No network, broker or production records.
import {PGlite} from '@electric-sql/pglite';
import {readFileSync} from 'node:fs';
import assert from 'node:assert/strict';
const db = new PGlite();
const q = (text, args=[]) => db.query(text, args);
const migration = name => readFileSync(new URL('../supabase/migrations/'+name, import.meta.url),'utf8');
await db.exec(readFileSync(new URL('migration_fixture.sql',import.meta.url),'utf8'));
// Reproduce the real creator's broad defaults and pre-existing event-table grant.
await db.exec(`alter default privileges in schema public grant all on tables to service_role;
alter default privileges in schema public grant execute on functions to service_role;
grant all on strategy_candidate_events to service_role;`);
await db.exec(migration('20260915234523_shadow_audit_remediation.sql'));
await db.exec(migration('20260916001258_discovery_state_acceptance_fix.sql'));
for (const table of ['strategy_candidate_events','strategy_discovery_events','journal_deliveries']) {
    assert.equal((await q('select has_table_privilege($1,$2,$3) allowed',['service_role',table,'DELETE'])).rows[0].allowed,true);
}
await db.exec(`set role service_role;
update strategy_candidates set operational_state='WAITING_FOR_TRIGGER',reason_code='LOCAL_FIXTURE';
insert into strategy_discovery_items(id,run_id,promotion_status) values
('00000000-0000-4000-8000-000000000003','00000000-0000-4000-8000-000000000001','REVIEW_REQUIRED');
insert into journal_deliveries(id,spreadsheet_id,status,patches,source_rows) values
('00000000-0000-4000-8000-000000000004','LOCAL-INFRASTRUCTURE-ONLY','PENDING','[{"range":"A1","value":"fixture"}]','[{"run_id":"local"}]');
reset role;`);
const tables = ['strategy_candidate_events','strategy_discovery_events','journal_deliveries'];
const snapshot = async () => Object.fromEntries(await Promise.all(tables.map(async table =>
    [table,(await q(`select to_jsonb(t) row from ${table} t order by id`)).rows])));
const before = await snapshot();
const correction = migration('20260917133500_restrict_audit_ledger_privileges.sql');
await db.exec(correction);
await db.exec(correction); // Safe reapplication of privileges, no schema/data replay.
assert.deepEqual(await snapshot(),before);
await db.exec('set role service_role;');
for (const table of tables) {
    await assert.rejects(()=>db.exec(`delete from ${table}`),/permission denied/i);
    await assert.rejects(()=>db.exec(`truncate ${table}`),/permission denied/i);
}
for (const table of tables.slice(0,2)) {
    await assert.rejects(()=>db.exec(`update ${table} set payload='{}'`),/permission denied/i);
}
await assert.rejects(()=>db.exec(`update journal_deliveries set patches='[]'`),/permission denied/i);
await assert.rejects(()=>db.exec(`update journal_deliveries set source_rows='[]'`),/permission denied/i);
await assert.rejects(()=>db.exec(`update journal_deliveries set spreadsheet_id='changed'`),/permission denied/i);
// Audit triggers must still fire atomically after function EXECUTE is revoked.
await db.exec(`update strategy_candidates set operational_state='HOLD_UNRESOLVED',reason_code='LOCAL_HOLD';
update strategy_discovery_items set operational_state='HOLD_UNRESOLVED';
update strategy_discovery_runs set status='COMPLETE';`);
assert.equal((await q('select count(*)::int n from strategy_candidate_events')).rows[0].n,2);
assert.equal((await q('select count(*)::int n from strategy_discovery_events')).rows[0].n,3);
// Preserve the pending barrier and both legitimate completion paths.
await assert.rejects(()=>db.exec(`insert into journal_deliveries(id,spreadsheet_id,status,patches,source_rows)
values(gen_random_uuid(),'LOCAL-INFRASTRUCTURE-ONLY','PENDING','[]','[]')`),/journal_one_unresolved_delivery/);
await db.exec(`update journal_deliveries set status='VERIFIED',verified_at=now()
where id='00000000-0000-4000-8000-000000000004';
insert into journal_deliveries(id,spreadsheet_id,status,patches,source_rows)
values('00000000-0000-4000-8000-000000000005','LOCAL-INFRASTRUCTURE-ONLY','PENDING','[]','[]');`);
await assert.rejects(()=>db.exec(`update journal_deliveries set status='RESOLVED_MANUALLY' where status='PENDING'`),/check constraint/i);
await db.exec(`update journal_deliveries set status='RESOLVED_MANUALLY',resolution_evidence='{"reviewer":"infrastructure-test","reason":"local only"}' where status='PENDING';
reset role;
alter table strategy_candidate_events add constraint reject_test_audit check(payload->>'reason'<>'FAIL_AUDIT');
set role service_role;`);
await assert.rejects(()=>db.exec(`update strategy_candidates set reason_code='FAIL_AUDIT'`),/reject_test_audit/);
assert.equal((await q('select reason_code from strategy_candidates')).rows[0].reason_code,'LOCAL_HOLD');
await db.exec('reset role;');
for (const role of ['anon','authenticated']) {
    await db.exec(`set role ${role};`);
    for (const table of tables) await assert.rejects(()=>q(`select * from ${table}`),/permission denied/i);
    await db.exec('reset role;');
}
await db.close();
console.log('Production-default privilege regression passed: bug reproduced, history preserved, append-only events, protected ledger evidence, trigger rollback and delivery completion.');
