import { PGlite } from '@electric-sql/pglite';
import { readFileSync } from 'node:fs';
import assert from 'node:assert/strict';

const db = new PGlite();
const query = (sql, args=[]) => db.query(sql, args);
await db.exec(readFileSync(new URL('migration_fixture.sql', import.meta.url), 'utf8'));
await db.exec(readFileSync(new URL('../supabase/migrations/20260915234523_shadow_audit_remediation.sql', import.meta.url), 'utf8'));

assert.equal((await query('select count(*)::int n from strategy_candidate_events')).rows[0].n, 0);
assert.equal((await query('select experiment_class from strategy_candidates')).rows[0].experiment_class, 'STRATEGY_1');
assert.equal((await query('select count(*)::int n from strategy_discovery_events')).rows[0].n, 0);
await db.exec(`set role service_role;
update strategy_candidates set operational_state='WAITING_FOR_TRIGGER',reason_code='TRIGGER_NOT_CONFIRMED',
run_id='00000000-0000-4000-8000-000000000001',transition_context='{"owner":"orchestrator","implementation_version":"test"}'
where id='00000000-0000-4000-8000-000000000002';`);
let events=(await query('select payload from strategy_candidate_events')).rows;
assert.equal(events.length,1);
assert.equal(events[0].payload.new_state,'WAITING_FOR_TRIGGER');
assert.equal(events[0].payload.run_id,'00000000-0000-4000-8000-000000000001');
await db.exec(`update strategy_candidates set operational_state='CONFIRMATION_REQUIRED' where id='00000000-0000-4000-8000-000000000002'`);
events=(await query('select payload from strategy_candidate_events')).rows;
assert.equal(events[1].payload.previous_state,'WAITING_FOR_TRIGGER');
assert.equal(events[1].payload.new_state,'CONFIRMATION_REQUIRED');
await db.exec(`insert into strategy_discovery_items(id,run_id,promotion_status) values
('00000000-0000-4000-8000-000000000003','00000000-0000-4000-8000-000000000001','REVIEW_REQUIRED');`);
assert.equal((await query('select count(*)::int n from strategy_discovery_events')).rows[0].n,1);
await assert.rejects(()=>db.exec('delete from strategy_discovery_events'),/permission denied/i);
await db.exec(`reset role; alter table strategy_candidate_events add constraint reject_audit check(payload->>'reason'<>'FAIL_AUDIT'); set role service_role;`);
await assert.rejects(()=>db.exec("update strategy_candidates set reason_code='FAIL_AUDIT',operational_state='TRADE_READY'"),/reject_audit/);
assert.equal((await query('select operational_state from strategy_candidates')).rows[0].operational_state,'CONFIRMATION_REQUIRED');
await db.exec(`insert into journal_deliveries(id,spreadsheet_id,status,patches,source_rows)
values('00000000-0000-4000-8000-000000000004','sheet','PENDING','[]','[]');`);
await assert.rejects(()=>db.exec(`insert into journal_deliveries(id,spreadsheet_id,status,patches,source_rows)
values('00000000-0000-4000-8000-000000000005','sheet','PENDING','[]','[]')`),/journal_one_unresolved_delivery/);
await assert.rejects(()=>db.exec(`update journal_deliveries set status='RESOLVED_MANUALLY'`),/check constraint/i);
await db.exec('reset role; set role anon;');
await assert.rejects(()=>query('select * from journal_deliveries'),/permission denied/i);
await assert.rejects(()=>query('select * from strategy_discovery_events'),/permission denied/i);
await db.close();
console.log('Migration checks passed: historical preservation, atomic audit rollback, role restrictions, pending-delivery uniqueness.');
